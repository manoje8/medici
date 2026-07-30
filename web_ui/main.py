import json
import os
import time
import uuid
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any

import logfire
import requests
import streamlit as st
from dotenv import load_dotenv

from src.common.utils.constants import ParseMethod

load_dotenv(override=True)


@dataclass(frozen=True)
class AppConfig:
    """Immutable application configuration with validation."""

    backend_url: str = field(
        default_factory=lambda: os.getenv("BACKEND_URL", "http://localhost:8000")
    )
    logfire_token: str | None = field(default_factory=lambda: os.getenv("LOGFIRE_TOKEN"))
    project_name: str = "Medici"

    ai_avatar: str = "🤖"
    user_avatar: str = "👤"
    page_title: str = "Medici - Agentic Assistant"
    layout: str = "wide"
    sidebar_state: str = "expanded"

    upload_timeout: int = 120
    query_timeout: int = 60
    connection_timeout: int = 10

    allowed_file_types: tuple[str, ...] = ("pdf", "txt", "md", "docx")
    max_file_size_mb: int = 50
    chunk_size: int = 1 * 1024 * 1024

    typing_speed: float = 0.005
    source_preview_length: int = 100

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.backend_url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid backend URL: {self.backend_url}")

        max_size_bytes = self.max_file_size_mb * 1024 * 1024
        object.__setattr__(self, "max_file_size_bytes", max_size_bytes)


class LoggingService:
    """Service for application logging and monitoring."""

    def __init__(self, config: AppConfig):
        self.config = config
        self._initialize()

    def _initialize(self) -> str:
        """Initialize Logfire with error handling."""
        try:
            if self.config.logfire_token:
                logfire.configure(
                    token=self.config.logfire_token,
                    service_name=self.config.project_name,
                )
                status = "Logfire connected"
            else:
                logfire.configure(
                    send_to_logfire=False,
                    service_name=self.config.project_name,
                )
                status = "⚠️ Logfire token missing - using local logging"

            logfire.info("Logging service initialized")
            return status

        except Exception as e:
            print(f"Logfire initialization error: {str(e)}")
            return f"❌ Logfire error: {str(e)}"

    def log_info(self, message: str, **kwargs):
        """Log informational message."""
        logfire.info(message, **kwargs)

    def log_warning(self, message: str, **kwargs):
        """Log warning message."""
        logfire.warn(message, **kwargs)

    def log_error(self, message: str, **kwargs):
        """Log error message."""
        logfire.error(message, **kwargs)

    def log_span(self, name: str, **kwargs):
        """Create a log span for tracing."""
        return logfire.span(name, **kwargs)


class BackendClient:
    """Client for backend API interactions with proper error handling."""

    def __init__(self, config: AppConfig, logger: LoggingService):
        self.config = config
        self.logger = logger
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a configured requests session."""
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": f"{self.config.project_name}/1.0",
                "Accept": "application/json",
            }
        )
        return session

    def _make_request(self, method: str, endpoint: str, timeout: int, **kwargs) -> dict[str, Any]:
        """Make HTTP request with error handling and logging."""
        url = f"{self.config.backend_url}/{endpoint.lstrip('/')}"

        try:
            with self.logger.log_span(f"API {method} {endpoint}"):
                response = self.session.request(method=method, url=url, timeout=timeout, **kwargs)
                response.raise_for_status()
                return response.json()

        except requests.exceptions.Timeout as tErr:
            self.logger.log_error(f"Request timeout: {endpoint}")
            raise TimeoutError(f"Request to {endpoint} timed out after {timeout}s") from tErr

        except requests.exceptions.ConnectionError as connErr:
            self.logger.log_error(f"Connection failed: {endpoint}")
            raise ConnectionError(
                f"Unable to connect to backend at {self.config.backend_url}"
            ) from connErr

        except requests.exceptions.HTTPError as e:
            self.logger.log_error(f"HTTP error: {endpoint}", status_code=e.response.status_code)
            raise RuntimeError(
                f"Backend returned error: {e.response.status_code} - {e.response.text}"
            ) from e

        except Exception as e:
            self.logger.log_error(f"Unexpected error: {endpoint}", error=str(e))
            raise

    def upload_document(self, file: Any, parse_method: str, doc_id: str) -> dict[str, Any]:
        """Upload a document to the backend."""
        return self._make_request(
            method="POST",
            endpoint="/ingestion",
            timeout=self.config.upload_timeout,
            files={"file": (file.name, file.getvalue(), file.type)},
            data={"parse_method": parse_method, "doc_id": doc_id},
        )

    def query(self, question: str, session_id: str, user_id: str) -> dict[str, Any]:
        """Send a query to the backend (non-streaming, kept for compatibility)."""
        return self._make_request(
            method="POST",
            endpoint="/query",
            timeout=self.config.query_timeout,
            json={
                "question": question,
                "session_id": session_id,
                "user_id": user_id,
            },
        )

    def query_stream(
        self, question: str, session_id: str, user_id: str
    ) -> Generator[dict[str, Any], None, None]:
        """
        Stream SSE events from ``POST /query/stream``.

        Yields parsed event dicts.  Stops after the ``done`` or ``error``
        event is received or when the connection drops.
        """
        url = f"{self.config.backend_url}/query/stream"
        payload = {"question": question, "session_id": session_id, "user_id": user_id}

        with self.logger.log_span("API POST /query/stream"):
            try:
                with self.session.post(
                    url,
                    json=payload,
                    stream=True,
                    timeout=self.config.query_timeout,
                ) as resp:
                    resp.raise_for_status()
                    for raw_line in resp.iter_lines(decode_unicode=True):
                        if not raw_line:
                            continue
                        if raw_line.startswith("data:"):
                            data_str = raw_line[len("data:") :].strip()
                            try:
                                event = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue
                            yield event
                            if event.get("type") in ("done", "error"):
                                return
            except requests.exceptions.Timeout as e:
                raise TimeoutError(
                    f"Stream request timed out after {self.config.query_timeout}s"
                ) from e
            except requests.exceptions.ConnectionError as e:
                raise ConnectionError(
                    f"Unable to connect to backend at {self.config.backend_url}"
                ) from e
            except requests.exceptions.HTTPError as e:
                raise RuntimeError(
                    f"Backend returned error: {e.response.status_code} - {e.response.text}"
                ) from e

    def health_check(self) -> dict[str, Any]:
        """Check backend health."""
        return self._make_request(
            method="GET",
            endpoint="/health",
            timeout=self.config.connection_timeout,
        )


class SessionStateManager:
    """Manages Streamlit session state with type safety."""

    @staticmethod
    def initialize(logger: LoggingService):
        """Initialize all session state variables."""
        defaults = {
            "session_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "messages": [],
            "uploaded_docs": [],
            "processing_message": False,
        }

        for key, default_value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default_value
                if key in ["session_id", "user_id"]:
                    logger.log_info(f"Initialized {key}", value=default_value[:8] + "...")

    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """Get a session state value safely."""
        return st.session_state.get(key, default)

    @staticmethod
    def set(key: str, value: Any):
        """Set a session state value."""
        st.session_state[key] = value

    @staticmethod
    def reset_session(logger: LoggingService):
        """Reset the chat session."""
        old_session_id = st.session_state.get("session_id", "unknown")
        logger.log_warning(f"Resetting session: {old_session_id[:8]}...")

        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.uploaded_docs = []
        st.session_state.processing_message = False


class SidebarRenderer:
    """Handles sidebar UI rendering."""

    def __init__(
        self,
        config: AppConfig,
        logger: LoggingService,
        api_client: BackendClient,
        state_manager: SessionStateManager,
    ):
        self.config = config
        self.logger = logger
        self.api_client = api_client
        self.state_manager = state_manager

    def render(self, logfire_status: str):
        """Render the complete sidebar."""
        with st.sidebar:
            self._render_status_section(logfire_status)
            st.divider()
            self._render_upload_section()
            st.divider()
            self._render_actions_section()
            st.divider()
            self._render_debug_section()

    def _render_status_section(self, logfire_status: str):
        """Render status indicators."""
        st.success(logfire_status)
        session_id = self.state_manager.get("session_id", "")
        st.info(f"🔑 Session: {session_id[:8]}...")

    def _render_upload_section(self):
        """Render document upload section."""
        st.subheader("📄 Document Upload")

        uploaded_file = st.file_uploader(
            "Choose a document",
            type=list(self.config.allowed_file_types),
            help=f"Supported formats: {', '.join(self.config.allowed_file_types)}",
            key="file_uploader",
        )

        if uploaded_file is not None:
            self._validate_and_display_file(uploaded_file)
            self._render_upload_options(uploaded_file)

    def _validate_and_display_file(self, file) -> bool:
        """Validate uploaded file and display info."""
        file_size_mb = len(file.getvalue()) / (1024 * 1024)

        if file_size_mb > self.config.max_file_size_mb:
            st.error(
                f"File too large: {file_size_mb:.1f}MB. "
                f"Maximum size: {self.config.max_file_size_mb}MB"
            )
            return False

        st.info(f"📎 {file.name} ({file_size_mb:.1f} MB)")
        return True

    def _render_upload_options(self, file):
        """Render upload parsing options and button."""
        parse_method = st.selectbox(
            "Parse Method",
            options=list(ParseMethod),
            format_func=lambda x: x.value.replace("_", " ").title(),
            index=1,
            key="parse_method_select",
        )

        if st.button(
            "📤 Upload Document",
            type="primary",
            use_container_width=True,
            key="upload_button",
            disabled=self.state_manager.get("processing_message", False),
        ):
            self._handle_document_upload(file, parse_method)

    def _handle_document_upload(self, file, parse_method):
        """Handle document upload with proper error handling."""
        doc_id = str(uuid.uuid4())

        with st.spinner(f"Processing {file.name}..."):
            try:
                with self.logger.log_span("Document upload", filename=file.name):
                    self.api_client.upload_document(
                        file=file,
                        parse_method=parse_method.value,
                        doc_id=doc_id,
                    )

                st.success(f"✅ Successfully processed: {file.name}")
                self.logger.log_info(
                    "Document uploaded successfully",
                    filename=file.name,
                    doc_id=doc_id[:8],
                )

                uploaded_docs = self.state_manager.get("uploaded_docs", [])
                uploaded_docs.append(
                    {
                        "name": file.name,
                        "doc_id": doc_id,
                        "method": parse_method.value,
                        "timestamp": time.time(),
                    }
                )
                self.state_manager.set("uploaded_docs", uploaded_docs)

            except (TimeoutError, ConnectionError, RuntimeError) as e:
                st.error(f"❌ Upload failed: {str(e)}")
                self.logger.log_error("Upload failed", error=str(e))

            except Exception as e:
                st.error(f"❌ Unexpected error: {str(e)}")
                self.logger.log_error("Upload unexpected error", error=str(e))

    def _render_actions_section(self):
        """Render action buttons."""
        st.subheader("⚙️ Actions")

        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                "Clear",
                use_container_width=True,
                key="clear_chat_button",
            ):
                self.state_manager.set("messages", [])
                st.rerun()

        with col2:
            if st.button(
                "New Session",
                use_container_width=True,
                key="new_session_button",
            ):
                self.state_manager.reset_session(self.logger)
                st.rerun()

    def _render_debug_section(self):
        """Render debug information section."""
        with st.expander("🔍 Debug Info", expanded=False):
            st.json(
                {
                    "session_id": self.state_manager.get("session_id", ""),
                    "user_id": self.state_manager.get("user_id", ""),
                    "message_count": len(self.state_manager.get("messages", [])),
                    "uploaded_docs": len(self.state_manager.get("uploaded_docs", [])),
                    "backend_url": self.config.backend_url,
                }
            )


class ChatRenderer:
    """Handles chat interface rendering."""

    def __init__(
        self,
        config: AppConfig,
        logger: LoggingService,
        api_client: BackendClient,
        state_manager: SessionStateManager,
    ):
        self.config = config
        self.logger = logger
        self.api_client = api_client
        self.state_manager = state_manager

    def render(self):
        """Render the complete chat interface."""
        self._render_message_history()
        self._render_chat_input()

    def _render_message_history(self):
        """Render all messages in chat history."""
        messages = self.state_manager.get("messages", [])

        if not messages:
            self._render_welcome_message()
            return

        for message in messages:
            avatar = (
                self.config.ai_avatar if message["role"] == "assistant" else self.config.user_avatar
            )
            with st.chat_message(message["role"], avatar=avatar):
                st.markdown(message["content"])

    def _render_welcome_message(self):
        """Render welcome message for new sessions."""
        with st.chat_message("assistant", avatar=self.config.ai_avatar):
            st.markdown("""
            👋 Welcome to **Medici Agentic Assistant**!

            I can help you with:
            - 📄 **Document Analysis**: Upload documents and ask questions about them
            - 💡 **Intelligent Queries**: Get detailed answers with source references
            - 🔍 **Context-Aware Responses**: I remember our conversation context

            Start by uploading a document or asking me a question!
            """)

    def _render_chat_input(self):
        """Render chat input with processing state handling."""
        if prompt := st.chat_input(
            "Ask me anything! 💭",
            disabled=self.state_manager.get("processing_message", False),
        ):
            self._process_user_message(prompt)

    def _process_user_message(self, prompt: str):
        """Process user message and get response."""
        if self.state_manager.get("processing_message", False):
            return

        self.state_manager.set("processing_message", True)

        try:
            with self.logger.log_span(
                "Chat interaction",
                user_query=prompt[:50] + "..." if len(prompt) > 50 else prompt,
            ):
                messages = self.state_manager.get("messages", [])
                messages.append({"role": "user", "content": prompt})
                self.state_manager.set("messages", messages)

                with st.chat_message("user", avatar=self.config.user_avatar):
                    st.markdown(prompt)

                self._get_and_display_response(prompt)

        finally:
            self.state_manager.set("processing_message", False)

    def _get_and_display_response(self, prompt: str):
        """Stream response from backend and display it progressively."""
        with st.chat_message("assistant", avatar=self.config.ai_avatar):
            self._fetch_and_stream_response(prompt)

    def _fetch_and_stream_response(self, prompt: str):
        """Consume the SSE stream and render pipeline stages + answer tokens."""
        status_placeholder = st.empty()
        answer_placeholder = st.empty()
        sources_placeholder = st.empty()

        collected_tokens: list[str] = []
        final_event: dict[str, Any] | None = None
        stage_lines: list[str] = []

        # Stage icons for pipeline progress
        _STAGE_ICONS: dict[str, str] = {
            "rewrite_query": "✏️",
            "route": "🔀",
            "plan": "📋",
            "retrieve": "🔍",
            "hop_check": "⚖️",
            "grade": "📊",
            "rewrite_for_refinement": "🔄",
            "synthesize": "✨",
            "direct_synthesize": "✨",
            "handle_simple_response": "💬",
        }

        def _render_status():
            if stage_lines:
                status_placeholder.markdown(
                    "\n".join(f"{line}" for line in stage_lines),
                    unsafe_allow_html=False,
                )

        try:
            for event in self.api_client.query_stream(
                question=prompt,
                session_id=self.state_manager.get("session_id"),
                user_id=self.state_manager.get("user_id"),
            ):
                etype = event.get("type")

                if etype == "progress":
                    node = event.get("node", "")
                    msg = event.get("message", "")
                    icon = _STAGE_ICONS.get(node, "⚙️")
                    stage_lines.append(f"{icon} {msg}…")
                    _render_status()

                elif etype == "token":
                    collected_tokens.append(event.get("content", ""))
                    answer_so_far = "".join(collected_tokens)
                    answer_placeholder.markdown(answer_so_far + "▌")

                elif etype == "done":
                    final_event = event
                    # Finalize answer (may come from cache or direct path)
                    if not collected_tokens:
                        answer = event.get("answer", "")
                        if answer:
                            self._display_animated_text_in(answer_placeholder, answer)
                    else:
                        answer_placeholder.markdown("".join(collected_tokens))

                elif etype == "error":
                    status_placeholder.empty()
                    st.error(f"⚠️ {event.get('message', 'Unknown error')}")
                    return

        except (TimeoutError, ConnectionError, RuntimeError) as e:
            status_placeholder.empty()
            st.error(f"⚠️ {str(e)}")
            self.logger.log_error("Stream response failed", error=str(e))
            return
        except Exception as e:
            status_placeholder.empty()
            st.error(f"⚠️ An unexpected error occurred: {str(e)}")
            self.logger.log_error("Unexpected stream error", error=str(e))
            return

        status_placeholder.empty()

        if final_event:
            answer = final_event.get("answer") or "".join(collected_tokens)
            sources = final_event.get("sources", [])

            if sources:
                with sources_placeholder.container():
                    self._display_sources(sources)

            messages = self.state_manager.get("messages", [])
            messages.append({"role": "assistant", "content": answer})
            self.state_manager.set("messages", messages)

            cache_hit = final_event.get("cache_hit", False)
            if cache_hit:
                st.caption("⚡ Served from semantic cache")

    def _display_animated_text_in(self, placeholder, text: str):
        """Animate text into a specific placeholder element."""
        displayed = ""
        for char in text:
            displayed += char
            placeholder.markdown(displayed + "▌")
            time.sleep(self.config.typing_speed)
        placeholder.markdown(text)

    def _fetch_response(self, prompt: str) -> dict[str, Any] | None:
        """Fetch response from backend with loading states."""
        with st.status("🧠 Processing your question...", expanded=True) as status:
            st.write("🔍 Analyzing query...")

            try:
                response = self.api_client.query(
                    question=prompt,
                    session_id=self.state_manager.get("session_id"),
                    user_id=self.state_manager.get("user_id"),
                )

                st.write("📚 Retrieving relevant context...")
                st.write("✨ Synthesizing answer...")

                status.update(
                    label="✅ Response generated",
                    state="complete",
                    expanded=False,
                )

                return response

            except (TimeoutError, ConnectionError) as e:
                status.update(label="❌ Connection failed", state="error")
                st.error(f"⚠️ {str(e)}")
                self.logger.log_error("Response fetch failed", error=str(e))
                return None

            except RuntimeError as e:
                status.update(label="❌ Backend error", state="error")
                st.error(f"⚠️ {str(e)}")
                self.logger.log_error("Backend error", error=str(e))
                return None

            except Exception as e:
                status.update(label="❌ Unexpected error", state="error")
                st.error(f"⚠️ An unexpected error occurred: {str(e)}")
                self.logger.log_error("Unexpected error in fetch", error=str(e))
                return None

    def _display_response(self, response: dict[str, Any]):
        """Display the assistant's response with sources."""
        answer = response.get("answer", "I apologize, but I couldn't generate a response.")
        sources = response.get("sources", [])

        if sources:
            self._display_sources(sources)

        self._display_animated_text(answer)

        messages = self.state_manager.get("messages", [])
        messages.append({"role": "assistant", "content": answer})
        self.state_manager.set("messages", messages)

    def _display_sources(self, sources: list[str]):
        """Display source context in expandable sections."""
        with st.expander("📚 View Retrieved Context Sources"):
            for i, source in enumerate(sources, 1):
                preview = source[: self.config.source_preview_length].replace("\n", " ")
                preview += "..." if len(source) > self.config.source_preview_length else ""

                with st.expander(f"Source {i}: {preview}"):
                    st.info(source)

    def _display_animated_text(self, text: str):
        """Display text with typing animation effect."""
        placeholder = st.empty()
        displayed_text = ""

        for char in text:
            displayed_text += char
            placeholder.markdown(displayed_text + "▌")
            time.sleep(self.config.typing_speed)

        placeholder.markdown(text)


class MediciApp:
    """Main application class orchestrating all components."""

    def __init__(self):
        self.config = AppConfig()
        self.logger = LoggingService(self.config)
        self.state_manager = SessionStateManager()

        self.state_manager.initialize(self.logger)

        self.api_client = BackendClient(self.config, self.logger)
        self.sidebar = SidebarRenderer(
            self.config, self.logger, self.api_client, self.state_manager
        )
        self.chat = ChatRenderer(self.config, self.logger, self.api_client, self.state_manager)

    def setup_page(self):
        """Configure Streamlit page settings."""
        st.set_page_config(
            page_title=self.config.page_title,
            page_icon="🤖",
            layout=self.config.layout,
            initial_sidebar_state=self.config.sidebar_state,
        )

    def check_backend_health(self) -> bool:
        """Check if backend is accessible."""
        try:
            self.api_client.health_check()
            return True
        except Exception:
            return False

    def run(self):
        """Run the main application."""
        self.setup_page()

        st.title(f"{self.config.project_name} 🤖")
        st.caption("Your Intelligent Document Analysis Assistant")

        logfire_status = self.logger._initialize()
        self.sidebar.render(logfire_status)

        if not self.check_backend_health():
            st.warning("⚠️ Backend service is not accessible. Some features may be limited.")
        else:
            self.chat.render()

        st.divider()
        st.caption(f"Session ID: {self.state_manager.get('session_id', '')[:8]}...")


def main():
    """Application entry point."""
    try:
        app = MediciApp()
        app.run()
    except Exception as e:
        st.error(f"Application Error: {str(e)}")
        st.stop()


if __name__ == "__main__":
    main()

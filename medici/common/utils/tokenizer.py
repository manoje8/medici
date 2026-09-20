from abc import ABC, abstractmethod


class TokenizerInterface(ABC):
    @abstractmethod
    def encode(self, content: str) -> list[int]:
        "Encodes a string into a list of tokens."
        ...

    @abstractmethod
    def decode(self, tokens: list[int]) -> str:
        "Decodes a list of tokens into a string."
        ...

    def count(self, content: str) -> int:
        """Returns the number of tokens in the string."""
        return len(self.encode(content))


class Tokenizer:
    def __init__(self, model_name: str, tokenizer: TokenizerInterface):
        self.model_name: str = model_name
        self.tokenizer: TokenizerInterface = tokenizer

    def encode(self, content: str) -> list[int]:
        try:
            return self.tokenizer.encode(content)
        except Exception as e:
            # Check if the error is about special tokens more reliably
            error_msg = str(e).lower()
            if "special token" not in error_msg and "special tokens" not in error_msg:
                raise

            try:
                return self.tokenizer.encode(content, allowed_special="all")
            except (TypeError, AttributeError):
                raise

    def decode(self, tokens: list[int]) -> str:
        return self.tokenizer.decode(tokens)

    def count(self, content: str) -> int:
        """Returns the number of tokens in the string."""
        return len(self.encode(content))


class TikTokenTokenizer(Tokenizer):
    """Token counter using OpenAI's tiktoken library.

    The default model (``gpt-4o-mini`` / cl100k_base encoding) is used as a
    **universal approximation** for token budgets, regardless of which LLM
    provider is actually serving requests.  This is a deliberate trade-off:

    * tiktoken is fast, deterministic, and works offline.
    * cl100k_base gives counts within ~10-30 % of most modern LLM tokenizers,
      which is accurate enough for chunk sizing and context-window guards —
      especially given the safety margin provided by ``MAX_PROMPT_OVERHEAD_TOKENS``.
    * Calling the real provider tokenizer for every chunk/budget check would
      add latency and external dependencies to the hot path.
    """

    def __init__(self, model_name: str = "gpt-4o-mini"):
        try:
            import tiktoken

        except ImportError as IE:
            raise ImportError(
                "tiktoken is not installed. Please install it with `pip install tiktoken`"
            ) from IE

        try:
            tokenizer = tiktoken.encoding_for_model(model_name=model_name)
            super().__init__(model_name=model_name, tokenizer=tokenizer)
        except KeyError as e:
            raise ValueError(f"Invalid model: {model_name}") from e

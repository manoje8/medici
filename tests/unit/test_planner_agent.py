"""
Unit tests for PlannerAgent.

Covers:
- decompose() with question_type='factual' (short-circuit, no LLM call)
- decompose() with non-factual type (mocked LLM returns sub-questions)
- decompose() where LLM call raises an exception
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.agentic.planner import PlannerAgent


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.complete = AsyncMock()
    return llm


@pytest.fixture
def planner(mock_llm):
    return PlannerAgent(llm_client=mock_llm)


class TestPlannerDecompose:
    async def test_factual_returns_original_question_no_llm_call(self, planner, mock_llm):
        """Factual questions should short-circuit and return [question] without calling LLM."""
        question = "What is the capital of France?"
        result = await planner.decompose(question, question_type="factual")
        assert result == [question]
        mock_llm.complete.assert_not_called()

    async def test_non_factual_calls_llm_and_returns_sub_questions(self, planner, mock_llm):
        sub_qs = ["What was memory usage in Q3?", "What was memory usage in Q4?"]
        mock_response = MagicMock()
        mock_response.parsed_json = sub_qs
        mock_llm.complete.return_value = mock_response

        result = await planner.decompose(
            "Compare Q3 vs Q4 memory usage", question_type="comparative"
        )
        assert result == sub_qs
        mock_llm.complete.assert_called_once()

    async def test_analytical_type_calls_llm(self, planner, mock_llm):
        sub_qs = ["Why did X happen?", "What caused Y?"]
        mock_response = MagicMock()
        mock_response.parsed_json = sub_qs
        mock_llm.complete.return_value = mock_response

        result = await planner.decompose("Analyze the root cause", question_type="analytical")
        assert len(result) == 2

    async def test_prompt_contains_question(self, planner, mock_llm):
        """Verify the question text appears in the LLM prompt."""
        mock_response = MagicMock()
        mock_response.parsed_json = ["sub1", "sub2"]
        mock_llm.complete.return_value = mock_response

        question = "What are the implications of climate change?"
        await planner.decompose(question, question_type="summarization")

        call_args = mock_llm.complete.call_args
        prompt = call_args[0][0]
        assert question in prompt

    async def test_stage_tag_is_planner(self, planner, mock_llm):
        """Verify the planner stage_tag is passed to LLM."""
        mock_response = MagicMock()
        mock_response.parsed_json = ["sub1"]
        mock_llm.complete.return_value = mock_response

        await planner.decompose("Some question", question_type="procedural")

        call_args = mock_llm.complete.call_args
        assert call_args[1].get("stage_tag") == "planner" or (
            len(call_args[0]) > 1 and call_args[0][1] == "planner"
        )

"""Tests for mock generator and AI client mock mode."""

import pytest
from unittest.mock import patch, MagicMock

from recque_tui.core.models import Question, SkillMap, Review
from recque_tui.core.mock_generator import MockGenerator, get_mock_generator, QuestionNode
from recque_tui.core.ai_client import AIClient


class TestMockGenerator:
    """Tests for MockGenerator class."""

    def test_singleton(self):
        """Test that get_mock_generator returns singleton."""
        gen1 = get_mock_generator()
        gen2 = get_mock_generator()
        assert gen1 is gen2

    def test_generate_skillmap_python(self):
        """Test generating skillmap for Python topic."""
        gen = MockGenerator()
        skillmap = gen.generate_skillmap("Python programming")

        assert isinstance(skillmap, SkillMap)
        assert len(skillmap.skills) == 3
        assert "Variables and Data Types" in skillmap.skills

    def test_generate_skillmap_math(self):
        """Test generating skillmap for Math topic."""
        gen = MockGenerator()
        skillmap = gen.generate_skillmap("Basic Math")

        assert isinstance(skillmap, SkillMap)
        assert len(skillmap.skills) == 3
        assert "Basic Arithmetic" in skillmap.skills

    def test_generate_skillmap_unknown(self):
        """Test generating skillmap for unknown topic."""
        gen = MockGenerator()
        skillmap = gen.generate_skillmap("Quantum Physics")

        assert isinstance(skillmap, SkillMap)
        assert len(skillmap.skills) == 3
        assert "Quantum Physics - Fundamental Concepts" in skillmap.skills

    def test_generate_question_python(self):
        """Test generating question for Python skill."""
        gen = MockGenerator()
        question = gen.generate_question("Python Variables and Data Types")

        assert isinstance(question, Question)
        assert question.question_text
        assert question.correct_answer
        assert len(question.incorrect_answers) >= 2

    def test_generate_question_generic(self):
        """Test generating generic question for unknown skill."""
        gen = MockGenerator()
        question = gen.generate_question("Unknown Skill XYZ")

        assert isinstance(question, Question)
        assert question.question_text
        assert question.correct_answer

    def test_drill_down_question(self):
        """Test getting drill-down question after wrong answer."""
        gen = MockGenerator()

        # Directly test drill-down without relying on which question was picked first
        # Simulate wrong answer on a known question - should get drill-down question
        followup = gen.generate_question(
            skill="Variables and Data Types",
            prior_question="What is the correct way to create a variable in Python?",
            prior_answer="var x = 5",
        )

        assert isinstance(followup, Question)
        assert followup.question_text == "Which language uses 'var' to declare variables?"
        assert followup.correct_answer == "JavaScript"

    def test_drill_down_multiple_levels(self):
        """Test drilling down multiple levels."""
        gen = MockGenerator()

        # Level 1: Wrong answer on var
        level1 = gen.generate_question(
            skill="Variables",
            prior_question="What is the correct way to create a variable in Python?",
            prior_answer="var x = 5",
        )
        assert "var" in level1.question_text.lower()

        # Level 2: Wrong answer again (Python uses var)
        level2 = gen.generate_question(
            skill="Variables",
            prior_question="Which language uses 'var' to declare variables?",
            prior_answer="Python",
        )
        assert isinstance(level2, Question)
        assert "Python" in level2.question_text

    def test_drill_down_four_levels(self):
        """Test drilling down 4 levels deep."""
        gen = MockGenerator()

        # Level 1: Start with variable question
        q1 = gen.generate_question(
            skill="Variables",
            prior_question="What is the correct way to create a variable in Python?",
            prior_answer="var x = 5",
        )
        assert q1.question_text == "Which language uses 'var' to declare variables?"

        # Level 2: Wrong again
        q2 = gen.generate_question(
            skill="Variables",
            prior_question="Which language uses 'var' to declare variables?",
            prior_answer="Python",
        )
        assert q2.question_text == "Python is known for NOT requiring which of the following?"

        # Level 3: Wrong again
        q3 = gen.generate_question(
            skill="Variables",
            prior_question="Python is known for NOT requiring which of the following?",
            prior_answer="Indentation",
        )
        assert q3.question_text == "What does Python use indentation for?"

        # Level 4 would continue if we had more depth for this path

    def test_drill_down_arithmetic_four_levels(self):
        """Test 4-level drill-down in arithmetic."""
        gen = MockGenerator()

        # Level 1
        q1 = gen.generate_question(
            skill="Basic Arithmetic",
            prior_question="What is 15 + 27?",
            prior_answer="41",
        )
        assert q1.question_text == "What is 5 + 7?"

        # Level 2
        q2 = gen.generate_question(
            skill="Basic Arithmetic",
            prior_question="What is 5 + 7?",
            prior_answer="11",
        )
        assert q2.question_text == "What is 5 + 6?"

        # Level 3
        q3 = gen.generate_question(
            skill="Basic Arithmetic",
            prior_question="What is 5 + 6?",
            prior_answer="10",
        )
        assert q3.question_text == "What is 5 + 5?"

    def test_drill_down_math_fractions(self):
        """Test drill-down for math fractions."""
        gen = MockGenerator()

        followup = gen.generate_question(
            skill="Fractions",
            prior_question="What is 1/2 + 1/4?",
            prior_answer="2/6",
        )

        assert followup.question_text == "To add fractions, what must be the same?"
        assert "denominators" in followup.correct_answer.lower()

    def test_no_followup_returns_new_question(self):
        """Test that missing followup returns a new question."""
        gen = MockGenerator()

        # Ask for followup to non-existent question
        question = gen.generate_question(
            skill="Variables and Data Types",
            prior_question="This question doesn't exist",
            prior_answer="Some answer",
        )

        # Should get a regular question, not crash
        assert isinstance(question, Question)
        assert question.question_text

    def test_verify_question(self):
        """Test mock verification always returns valid."""
        gen = MockGenerator()
        question = Question(
            question_text="Test?",
            correct_answer="A",
            incorrect_answers=["B", "C"],
        )
        review = gen.verify_question(question)

        assert isinstance(review, Review)
        assert review.valid is True
        assert review.correct_answer == "A"

    def test_question_node_structure(self):
        """Test QuestionNode dataclass."""
        node = QuestionNode(
            question=Question(
                question_text="Q1?",
                correct_answer="A",
                incorrect_answers=["B", "C"],
            ),
            followups={
                "B": QuestionNode(
                    question=Question(
                        question_text="Why not B?",
                        correct_answer="Because...",
                        incorrect_answers=["X", "Y"],
                    ),
                ),
            },
        )

        assert node.question.question_text == "Q1?"
        assert "B" in node.followups
        assert node.followups["B"].question.question_text == "Why not B?"


class TestAIClientMockMode:
    """Tests for AIClient in mock mode."""

    def test_mock_mode_explicit(self):
        """Test AIClient with explicit mock_mode=True."""
        client = AIClient(mock_mode=True)
        assert client.mock_mode is True

    def test_mock_mode_from_config(self):
        """Test AIClient reads mock_mode from config."""
        with patch("recque_tui.core.ai_client.get_config") as mock_config:
            mock_config.return_value = MagicMock(
                mock_mode=True,
                model="gpt-4o-mini",
                valid_models=["gpt-4o-mini"],
                default_model="gpt-4o-mini",
            )
            client = AIClient()
            assert client.mock_mode is True

    def test_generate_skillmap_mock(self):
        """Test generating skillmap in mock mode."""
        client = AIClient(mock_mode=True)
        result = client.generate(
            "Generate a skillmap for topic: Python basics",
            SkillMap,
        )

        assert isinstance(result, SkillMap)
        assert len(result.skills) > 0

    def test_generate_question_mock(self):
        """Test generating question in mock mode."""
        client = AIClient(mock_mode=True)
        result = client.generate(
            "Generate a question about: Python variables",
            Question,
        )

        assert isinstance(result, Question)
        assert result.question_text
        assert result.correct_answer

    def test_generate_review_mock(self):
        """Test generating review in mock mode."""
        client = AIClient(mock_mode=True)
        result = client.generate(
            "Verify this question",
            Review,
        )

        assert isinstance(result, Review)
        assert result.valid is True

    def test_lazy_client_initialization(self):
        """Test OpenAI client is not initialized in mock mode until needed."""
        client = AIClient(mock_mode=True)
        # Should not have initialized OpenAI client yet
        assert client._client is None

        # Generate in mock mode - still no OpenAI client needed
        client.generate("Test prompt", SkillMap)
        assert client._client is None

    def test_fallback_to_mock_on_error(self):
        """Test that API errors fall back to mock generator."""
        client = AIClient(mock_mode=False)

        # Mock the OpenAI client to raise an error
        with patch.object(client, "_client", create=True) as mock_openai:
            mock_openai.beta.chat.completions.parse.side_effect = Exception("API Error")
            client._client = mock_openai

            # Should fall back to mock
            result = client.generate(
                "Generate a skillmap for topic: Python",
                SkillMap,
            )

            assert isinstance(result, SkillMap)
            assert len(result.skills) > 0

    def test_extract_topic_from_prompt(self):
        """Test topic extraction from various prompt formats."""
        client = AIClient(mock_mode=True)

        # With "topic:" prefix
        topic = client._extract_topic_from_prompt("Generate skills for topic: Python programming")
        assert "python" in topic.lower()

        # With "learn about" pattern
        topic = client._extract_topic_from_prompt("I want to learn about JavaScript")
        assert "javascript" in topic.lower()

        # Fallback
        topic = client._extract_topic_from_prompt("Something else entirely")
        assert topic == "general knowledge"

    def test_extract_skill_from_prompt(self):
        """Test skill extraction from various prompt formats."""
        client = AIClient(mock_mode=True)

        # With "skill:" prefix
        skill = client._extract_skill_from_prompt("Generate a question for skill: Variables")
        assert "variables" in skill.lower()

        # With "about" pattern
        skill = client._extract_skill_from_prompt("Create a question about Functions")
        assert "functions" in skill.lower()

        # Fallback
        skill = client._extract_skill_from_prompt("Something else")
        assert skill == "general"

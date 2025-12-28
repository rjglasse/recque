"""Mock question and skill generator for offline/testing mode."""

import random
from dataclasses import dataclass, field
from typing import ClassVar

from recque_tui.core.models import Question, SkillMap, Review


@dataclass
class QuestionNode:
    """A question with optional drill-down questions for wrong answers."""

    question: Question
    # Maps incorrect answer -> follow-up question that explains why it's wrong
    followups: dict[str, "QuestionNode"] = field(default_factory=dict)


class MockGenerator:
    """Generates mock questions and skills for testing without API access."""

    # Question trees with drill-down questions (3+ levels deep)
    QUESTION_TREES: ClassVar[dict[str, list[QuestionNode]]] = {
        "variables and data types": [
            QuestionNode(
                question=Question(
                    question_text="What is the correct way to create a variable in Python?",
                    correct_answer="x = 5",
                    incorrect_answers=["var x = 5", "int x = 5", "let x = 5"],
                ),
                followups={
                    "var x = 5": QuestionNode(
                        question=Question(
                            question_text="Which language uses 'var' to declare variables?",
                            correct_answer="JavaScript",
                            incorrect_answers=["Python", "Ruby", "Go"],
                        ),
                        followups={
                            "Python": QuestionNode(
                                question=Question(
                                    question_text="Python is known for NOT requiring which of the following?",
                                    correct_answer="Variable declaration keywords",
                                    incorrect_answers=["Indentation", "Colons after if statements", "Import statements"],
                                ),
                                followups={
                                    "Indentation": QuestionNode(
                                        question=Question(
                                            question_text="What does Python use indentation for?",
                                            correct_answer="To define code blocks",
                                            incorrect_answers=["Just for readability", "To declare variables", "To end statements"],
                                        ),
                                    ),
                                },
                            ),
                            "Ruby": QuestionNode(
                                question=Question(
                                    question_text="How do you declare a local variable in Ruby?",
                                    correct_answer="Just assign it: x = 5",
                                    incorrect_answers=["var x = 5", "local x = 5", "def x = 5"],
                                ),
                            ),
                        },
                    ),
                    "int x = 5": QuestionNode(
                        question=Question(
                            question_text="Which language requires type declarations like 'int x = 5'?",
                            correct_answer="C/C++",
                            incorrect_answers=["Python", "Ruby", "JavaScript"],
                        ),
                        followups={
                            "Python": QuestionNode(
                                question=Question(
                                    question_text="Python is a statically or dynamically typed language?",
                                    correct_answer="Dynamically typed",
                                    incorrect_answers=["Statically typed", "Both", "Neither"],
                                ),
                                followups={
                                    "Statically typed": QuestionNode(
                                        question=Question(
                                            question_text="In static typing, when are types checked?",
                                            correct_answer="At compile time",
                                            incorrect_answers=["At runtime", "Never", "Only on errors"],
                                        ),
                                    ),
                                },
                            ),
                        },
                    ),
                    "let x = 5": QuestionNode(
                        question=Question(
                            question_text="'let' is a variable keyword in which language?",
                            correct_answer="JavaScript (ES6)",
                            incorrect_answers=["Python 3", "Java", "C#"],
                        ),
                        followups={
                            "Python 3": QuestionNode(
                                question=Question(
                                    question_text="What keyword does Python 3 NOT have?",
                                    correct_answer="let, var, const",
                                    incorrect_answers=["def, class, import", "if, else, elif", "for, while, break"],
                                ),
                            ),
                        },
                    ),
                },
            ),
            QuestionNode(
                question=Question(
                    question_text="Which of the following is an immutable data type in Python?",
                    correct_answer="tuple",
                    incorrect_answers=["list", "dictionary", "set"],
                ),
                followups={
                    "list": QuestionNode(
                        question=Question(
                            question_text="What operation can you do with a list but NOT a tuple?",
                            correct_answer="Append new items",
                            incorrect_answers=["Access by index", "Iterate with a loop", "Check length"],
                        ),
                        followups={
                            "Access by index": QuestionNode(
                                question=Question(
                                    question_text="What does my_tuple[0] do?",
                                    correct_answer="Returns the first element",
                                    incorrect_answers=["Causes an error", "Returns the last element", "Returns the length"],
                                ),
                                followups={
                                    "Causes an error": QuestionNode(
                                        question=Question(
                                            question_text="Which operation DOES cause an error on a tuple?",
                                            correct_answer="my_tuple[0] = 'new_value'",
                                            incorrect_answers=["my_tuple[0]", "len(my_tuple)", "for x in my_tuple"],
                                        ),
                                    ),
                                },
                            ),
                        },
                    ),
                    "dictionary": QuestionNode(
                        question=Question(
                            question_text="What makes dictionaries mutable?",
                            correct_answer="You can add, remove, or change key-value pairs",
                            incorrect_answers=["They use curly braces", "They store key-value pairs", "They are unordered"],
                        ),
                        followups={
                            "They use curly braces": QuestionNode(
                                question=Question(
                                    question_text="What else in Python uses curly braces?",
                                    correct_answer="Sets",
                                    incorrect_answers=["Lists", "Tuples", "Strings"],
                                ),
                                followups={
                                    "Lists": QuestionNode(
                                        question=Question(
                                            question_text="What brackets do Python lists use?",
                                            correct_answer="Square brackets []",
                                            incorrect_answers=["Curly braces {}", "Parentheses ()", "Angle brackets <>"],
                                        ),
                                    ),
                                },
                            ),
                        },
                    ),
                    "set": QuestionNode(
                        question=Question(
                            question_text="Which operation proves that sets are mutable?",
                            correct_answer="set.add(item)",
                            incorrect_answers=["len(set)", "item in set", "for x in set"],
                        ),
                        followups={
                            "len(set)": QuestionNode(
                                question=Question(
                                    question_text="Does len() modify the object it measures?",
                                    correct_answer="No, it only reads the length",
                                    incorrect_answers=["Yes, it updates internal state", "Sometimes", "Only for mutable types"],
                                ),
                            ),
                        },
                    ),
                },
            ),
        ],
        "control flow": [
            QuestionNode(
                question=Question(
                    question_text="Which keyword is used to skip the current iteration in a loop?",
                    correct_answer="continue",
                    incorrect_answers=["break", "pass", "skip"],
                ),
                followups={
                    "break": QuestionNode(
                        question=Question(
                            question_text="What does 'break' do in a loop?",
                            correct_answer="Exits the loop entirely",
                            incorrect_answers=["Skips to next iteration", "Pauses the loop", "Restarts the loop"],
                        ),
                        followups={
                            "Skips to next iteration": QuestionNode(
                                question=Question(
                                    question_text="Which keyword skips to the next iteration?",
                                    correct_answer="continue",
                                    incorrect_answers=["break", "next", "skip"],
                                ),
                                followups={
                                    "next": QuestionNode(
                                        question=Question(
                                            question_text="What does next() do in Python?",
                                            correct_answer="Gets the next item from an iterator",
                                            incorrect_answers=["Skips loop iteration", "Moves to next line", "Increments a counter"],
                                        ),
                                    ),
                                },
                            ),
                            "Pauses the loop": QuestionNode(
                                question=Question(
                                    question_text="How can you pause execution in Python?",
                                    correct_answer="time.sleep(seconds)",
                                    incorrect_answers=["pause()", "wait()", "break"],
                                ),
                            ),
                        },
                    ),
                    "pass": QuestionNode(
                        question=Question(
                            question_text="What is 'pass' used for in Python?",
                            correct_answer="A placeholder that does nothing",
                            incorrect_answers=["Skip iteration", "Exit loop", "Return a value"],
                        ),
                        followups={
                            "Skip iteration": QuestionNode(
                                question=Question(
                                    question_text="If 'pass' doesn't skip, what DOES it do?",
                                    correct_answer="Absolutely nothing - it's a no-op",
                                    incorrect_answers=["Logs a message", "Raises an exception", "Returns None"],
                                ),
                                followups={
                                    "Raises an exception": QuestionNode(
                                        question=Question(
                                            question_text="Which keyword explicitly raises an exception?",
                                            correct_answer="raise",
                                            incorrect_answers=["throw", "error", "exception"],
                                        ),
                                    ),
                                },
                            ),
                        },
                    ),
                    "skip": QuestionNode(
                        question=Question(
                            question_text="Is 'skip' a Python keyword?",
                            correct_answer="No, it's not a Python keyword",
                            incorrect_answers=["Yes, it skips iterations", "Yes, it's an alias for continue", "Yes, but it's deprecated"],
                        ),
                        followups={
                            "Yes, it skips iterations": QuestionNode(
                                question=Question(
                                    question_text="Which of these IS a Python keyword?",
                                    correct_answer="continue",
                                    incorrect_answers=["skip", "next", "jump"],
                                ),
                            ),
                        },
                    ),
                },
            ),
        ],
        "functions": [
            QuestionNode(
                question=Question(
                    question_text="Which keyword is used to define a function in Python?",
                    correct_answer="def",
                    incorrect_answers=["function", "func", "define"],
                ),
                followups={
                    "function": QuestionNode(
                        question=Question(
                            question_text="Which language uses 'function' as a keyword?",
                            correct_answer="JavaScript",
                            incorrect_answers=["Python", "C", "Go"],
                        ),
                        followups={
                            "Python": QuestionNode(
                                question=Question(
                                    question_text="What 3-letter keyword defines functions in Python?",
                                    correct_answer="def",
                                    incorrect_answers=["fun", "fnc", "sub"],
                                ),
                                followups={
                                    "fun": QuestionNode(
                                        question=Question(
                                            question_text="Which language uses 'fun' for functions?",
                                            correct_answer="Kotlin",
                                            incorrect_answers=["Python", "Java", "C++"],
                                        ),
                                    ),
                                },
                            ),
                        },
                    ),
                    "func": QuestionNode(
                        question=Question(
                            question_text="Which language uses 'func' to define functions?",
                            correct_answer="Go",
                            incorrect_answers=["Python", "Java", "C++"],
                        ),
                        followups={
                            "Python": QuestionNode(
                                question=Question(
                                    question_text="Go and Python differ in typing. Go is:",
                                    correct_answer="Statically typed",
                                    incorrect_answers=["Dynamically typed", "Untyped", "Weakly typed"],
                                ),
                            ),
                        },
                    ),
                    "define": QuestionNode(
                        question=Question(
                            question_text="In Python, 'def' is short for what word?",
                            correct_answer="define",
                            incorrect_answers=["default", "defer", "definition"],
                        ),
                        followups={
                            "default": QuestionNode(
                                question=Question(
                                    question_text="How do you set a default parameter value in Python?",
                                    correct_answer="def func(x=10):",
                                    incorrect_answers=["def func(x: 10):", "def func(default x=10):", "def func(x default 10):"],
                                ),
                            ),
                        },
                    ),
                },
            ),
            QuestionNode(
                question=Question(
                    question_text="What does a function return if no return statement is specified?",
                    correct_answer="None",
                    incorrect_answers=["0", "False", "An empty string"],
                ),
                followups={
                    "0": QuestionNode(
                        question=Question(
                            question_text="In Python, what is the difference between 0 and None?",
                            correct_answer="0 is an integer, None represents absence of value",
                            incorrect_answers=["They are the same", "0 is falsy, None is truthy", "None equals 0 in comparisons"],
                        ),
                        followups={
                            "They are the same": QuestionNode(
                                question=Question(
                                    question_text="What does '0 == None' evaluate to?",
                                    correct_answer="False",
                                    incorrect_answers=["True", "None", "Raises an error"],
                                ),
                                followups={
                                    "True": QuestionNode(
                                        question=Question(
                                            question_text="What does '0 is None' evaluate to?",
                                            correct_answer="False (they are different objects)",
                                            incorrect_answers=["True", "None", "Raises TypeError"],
                                        ),
                                    ),
                                },
                            ),
                        },
                    ),
                    "False": QuestionNode(
                        question=Question(
                            question_text="What is the boolean value of None in Python?",
                            correct_answer="Falsy (evaluates to False in boolean context)",
                            incorrect_answers=["True", "It causes an error", "Neither True nor False"],
                        ),
                        followups={
                            "True": QuestionNode(
                                question=Question(
                                    question_text="Which of these is truthy in Python?",
                                    correct_answer="[1] (non-empty list)",
                                    incorrect_answers=["None", "0", "'' (empty string)"],
                                ),
                                followups={
                                    "None": QuestionNode(
                                        question=Question(
                                            question_text="What is the ONLY truthy value here?",
                                            correct_answer="1",
                                            incorrect_answers=["0", "None", "False"],
                                        ),
                                    ),
                                },
                            ),
                        },
                    ),
                    "An empty string": QuestionNode(
                        question=Question(
                            question_text="What is the boolean value of an empty string ''?",
                            correct_answer="Falsy (evaluates to False)",
                            incorrect_answers=["Truthy", "None", "Raises an error"],
                        ),
                        followups={
                            "Truthy": QuestionNode(
                                question=Question(
                                    question_text="Which string IS truthy?",
                                    correct_answer="'hello' (any non-empty string)",
                                    incorrect_answers=["'' (empty)", "'0' is falsy", "All strings are falsy"],
                                ),
                            ),
                        },
                    ),
                },
            ),
        ],
        "basic arithmetic": [
            QuestionNode(
                question=Question(
                    question_text="What is 15 + 27?",
                    correct_answer="42",
                    incorrect_answers=["41", "43", "52"],
                ),
                followups={
                    "41": QuestionNode(
                        question=Question(
                            question_text="What is 5 + 7?",
                            correct_answer="12",
                            incorrect_answers=["11", "13", "10"],
                        ),
                        followups={
                            "11": QuestionNode(
                                question=Question(
                                    question_text="What is 5 + 6?",
                                    correct_answer="11",
                                    incorrect_answers=["10", "12", "13"],
                                ),
                                followups={
                                    "10": QuestionNode(
                                        question=Question(
                                            question_text="What is 5 + 5?",
                                            correct_answer="10",
                                            incorrect_answers=["9", "11", "12"],
                                        ),
                                    ),
                                },
                            ),
                        },
                    ),
                    "52": QuestionNode(
                        question=Question(
                            question_text="When adding 15 + 27, what do you carry over?",
                            correct_answer="1 (from 5+7=12)",
                            incorrect_answers=["0", "2", "Nothing"],
                        ),
                        followups={
                            "0": QuestionNode(
                                question=Question(
                                    question_text="When do you carry in addition?",
                                    correct_answer="When the sum of digits is 10 or more",
                                    incorrect_answers=["Never", "Always", "Only with 3+ digit numbers"],
                                ),
                                followups={
                                    "Never": QuestionNode(
                                        question=Question(
                                            question_text="What is 9 + 5?",
                                            correct_answer="14 (carry the 1)",
                                            incorrect_answers=["13", "15", "95"],
                                        ),
                                    ),
                                },
                            ),
                        },
                    ),
                    "43": QuestionNode(
                        question=Question(
                            question_text="Let's break it down: 15 + 27 = 15 + 20 + 7 = ?",
                            correct_answer="35 + 7 = 42",
                            incorrect_answers=["35 + 7 = 43", "35 + 7 = 41", "36 + 7 = 43"],
                        ),
                    ),
                },
            ),
        ],
        "fractions": [
            QuestionNode(
                question=Question(
                    question_text="What is 1/2 + 1/4?",
                    correct_answer="3/4",
                    incorrect_answers=["2/6", "1/3", "2/4"],
                ),
                followups={
                    "2/6": QuestionNode(
                        question=Question(
                            question_text="To add fractions, what must be the same?",
                            correct_answer="The denominators",
                            incorrect_answers=["The numerators", "Both numbers", "Nothing special"],
                        ),
                        followups={
                            "The numerators": QuestionNode(
                                question=Question(
                                    question_text="In a fraction a/b, which is the denominator?",
                                    correct_answer="b (the bottom number)",
                                    incorrect_answers=["a (the top number)", "Both a and b", "Neither"],
                                ),
                                followups={
                                    "a (the top number)": QuestionNode(
                                        question=Question(
                                            question_text="In 3/4, what is the numerator?",
                                            correct_answer="3",
                                            incorrect_answers=["4", "3/4", "0.75"],
                                        ),
                                    ),
                                },
                            ),
                            "Nothing special": QuestionNode(
                                question=Question(
                                    question_text="Why can't you add 1/2 + 1/3 directly?",
                                    correct_answer="Different denominators - need common denominator first",
                                    incorrect_answers=["You can: 1/2 + 1/3 = 2/5", "Fractions can't be added", "Only whole numbers add"],
                                ),
                                followups={
                                    "You can: 1/2 + 1/3 = 2/5": QuestionNode(
                                        question=Question(
                                            question_text="What is the common denominator of 2 and 3?",
                                            correct_answer="6",
                                            incorrect_answers=["5", "1", "23"],
                                        ),
                                    ),
                                },
                            ),
                        },
                    ),
                    "2/4": QuestionNode(
                        question=Question(
                            question_text="What is 1/2 expressed with denominator 4?",
                            correct_answer="2/4",
                            incorrect_answers=["1/4", "4/2", "3/4"],
                        ),
                        followups={
                            "1/4": QuestionNode(
                                question=Question(
                                    question_text="To convert 1/2 to fourths, multiply top and bottom by?",
                                    correct_answer="2 (giving 2/4)",
                                    incorrect_answers=["4", "1/2", "Nothing"],
                                ),
                                followups={
                                    "4": QuestionNode(
                                        question=Question(
                                            question_text="What is 1/2 × 4/4?",
                                            correct_answer="4/8 (which equals 1/2)",
                                            incorrect_answers=["4/2", "1/8", "2/4"],
                                        ),
                                    ),
                                },
                            ),
                        },
                    ),
                    "1/3": QuestionNode(
                        question=Question(
                            question_text="Is 1/3 greater or less than 1/4?",
                            correct_answer="Greater (1/3 > 1/4)",
                            incorrect_answers=["Less", "Equal", "Can't compare fractions"],
                        ),
                        followups={
                            "Less": QuestionNode(
                                question=Question(
                                    question_text="If you divide a pizza into 3 vs 4 slices, which slice is bigger?",
                                    correct_answer="The 1/3 slice (fewer pieces = bigger pieces)",
                                    incorrect_answers=["The 1/4 slice", "They're equal", "Depends on pizza size"],
                                ),
                            ),
                        },
                    ),
                },
            ),
        ],
        "order of operations": [
            QuestionNode(
                question=Question(
                    question_text="What is 2 + 3 × 4?",
                    correct_answer="14",
                    incorrect_answers=["20", "24", "12"],
                ),
                followups={
                    "20": QuestionNode(
                        question=Question(
                            question_text="In order of operations, which comes first?",
                            correct_answer="Multiplication before addition",
                            incorrect_answers=["Addition before multiplication", "Left to right always", "Right to left always"],
                        ),
                        followups={
                            "Addition before multiplication": QuestionNode(
                                question=Question(
                                    question_text="What does PEMDAS stand for?",
                                    correct_answer="Parentheses, Exponents, Multiplication, Division, Addition, Subtraction",
                                    incorrect_answers=[
                                        "Plus, Equals, Minus, Divide, Add, Subtract",
                                        "Parentheses, Equations, Math, Division, Addition, Subtraction",
                                        "Priority, Exponents, Multiply, Divide, Add, Subtract",
                                    ],
                                ),
                                followups={
                                    "Plus, Equals, Minus, Divide, Add, Subtract": QuestionNode(
                                        question=Question(
                                            question_text="What does the P in PEMDAS stand for?",
                                            correct_answer="Parentheses",
                                            incorrect_answers=["Plus", "Power", "Priority"],
                                        ),
                                    ),
                                },
                            ),
                            "Left to right always": QuestionNode(
                                question=Question(
                                    question_text="What is 10 - 3 + 2 using left-to-right?",
                                    correct_answer="9 (same level, so left-to-right is correct here)",
                                    incorrect_answers=["5", "15", "7"],
                                ),
                                followups={
                                    "5": QuestionNode(
                                        question=Question(
                                            question_text="What is 10 - 3?",
                                            correct_answer="7",
                                            incorrect_answers=["8", "6", "13"],
                                        ),
                                    ),
                                },
                            ),
                        },
                    ),
                    "24": QuestionNode(
                        question=Question(
                            question_text="You calculated (2+3) × 4 = 24. What's different about 2 + 3 × 4?",
                            correct_answer="No parentheses, so multiply first: 2 + 12 = 14",
                            incorrect_answers=["They're the same", "Add first always", "Multiply the smaller numbers first"],
                        ),
                        followups={
                            "They're the same": QuestionNode(
                                question=Question(
                                    question_text="What do parentheses do in math?",
                                    correct_answer="Force that operation to happen first",
                                    incorrect_answers=["Nothing, just decoration", "Make numbers negative", "Group equal values"],
                                ),
                                followups={
                                    "Nothing, just decoration": QuestionNode(
                                        question=Question(
                                            question_text="What is (5) × 2?",
                                            correct_answer="10 (parentheses around single number don't change it)",
                                            incorrect_answers=["52", "-10", "Error"],
                                        ),
                                    ),
                                },
                            ),
                        },
                    ),
                },
            ),
        ],
    }

    # Topic -> skill mappings
    TOPIC_SKILLS: ClassVar[dict[str, list[str]]] = {
        "python": ["Variables and Data Types", "Control Flow", "Functions"],
        "math": ["Basic Arithmetic", "Fractions", "Order of Operations"],
    }

    # Generic skills for unknown topics
    GENERIC_SKILLS: ClassVar[list[str]] = [
        "Fundamental Concepts",
        "Core Principles",
        "Practical Applications",
    ]

    # Generic question trees for unknown topics
    GENERIC_TREES: ClassVar[list[QuestionNode]] = [
        QuestionNode(
            question=Question(
                question_text="Which approach is generally recommended for learning new concepts?",
                correct_answer="Start with basics and build up gradually",
                incorrect_answers=[
                    "Jump straight to advanced topics",
                    "Memorize everything at once",
                    "Skip the theory entirely",
                ],
            ),
            followups={
                "Jump straight to advanced topics": QuestionNode(
                    question=Question(
                        question_text="Why might skipping basics cause problems?",
                        correct_answer="Advanced topics often build on foundational knowledge",
                        incorrect_answers=[
                            "It doesn't cause problems",
                            "Basics are always harder",
                            "Teachers prefer it that way",
                        ],
                    ),
                ),
                "Memorize everything at once": QuestionNode(
                    question=Question(
                        question_text="What is more effective than pure memorization?",
                        correct_answer="Understanding concepts and applying them",
                        incorrect_answers=[
                            "Reading faster",
                            "Using flashcards only",
                            "Studying longer hours",
                        ],
                    ),
                ),
            },
        ),
        QuestionNode(
            question=Question(
                question_text="What is the best way to retain new information?",
                correct_answer="Practice regularly with spaced repetition",
                incorrect_answers=[
                    "Read it once and move on",
                    "Highlight everything in the textbook",
                    "Only study the night before a test",
                ],
            ),
            followups={
                "Read it once and move on": QuestionNode(
                    question=Question(
                        question_text="What does the 'forgetting curve' describe?",
                        correct_answer="How quickly we forget information without review",
                        incorrect_answers=[
                            "A type of learning disability",
                            "A graph of test scores",
                            "Memory improvement over time",
                        ],
                    ),
                ),
            },
        ),
    ]

    def __init__(self):
        """Initialize the mock generator."""
        self._used_questions: set[str] = set()

    def generate_skillmap(self, topic: str) -> SkillMap:
        """Generate a mock skillmap for a topic."""
        topic_lower = topic.lower()

        for key, skills in self.TOPIC_SKILLS.items():
            if key in topic_lower:
                return SkillMap(skills=skills)

        return SkillMap(
            skills=[f"{topic} - {skill}" for skill in self.GENERIC_SKILLS]
        )

    def generate_question(
        self,
        skill: str,
        prior_question: str | None = None,
        prior_answer: str | None = None,
        variation: bool = False,
    ) -> Question:
        """Generate a mock question with drill-down support.

        Args:
            skill: The skill to generate a question for.
            prior_question: Previous question text (for drill-down).
            prior_answer: The incorrect answer given (for drill-down).
            variation: Whether to generate a variation.

        Returns:
            A mock Question - either a drill-down or a new top-level question.
        """
        skill_lower = skill.lower()

        # If we have a prior question/answer, try to find a drill-down question
        if prior_question and prior_answer:
            followup = self._find_followup(prior_question, prior_answer)
            if followup:
                return followup.question

        # Find question trees for this skill
        trees = self._get_trees_for_skill(skill_lower)

        if trees:
            # Pick a random question, avoiding recently used ones if possible
            available = [t for t in trees if t.question.question_text not in self._used_questions]
            if not available:
                self._used_questions.clear()
                available = trees

            node = random.choice(available)
            self._used_questions.add(node.question.question_text)
            return node.question

        # Fallback to generic
        return self._get_generic_question()

    def _get_trees_for_skill(self, skill_lower: str) -> list[QuestionNode]:
        """Get question trees matching a skill."""
        for skill_key, trees in self.QUESTION_TREES.items():
            if skill_key in skill_lower or skill_lower in skill_key:
                return trees
        return []

    def _find_followup(self, prior_question: str, prior_answer: str) -> QuestionNode | None:
        """Find a follow-up question for a wrong answer."""
        # Search all question trees
        for trees in self.QUESTION_TREES.values():
            for tree in trees:
                result = self._search_tree(tree, prior_question, prior_answer)
                if result:
                    return result

        # Check generic trees too
        for tree in self.GENERIC_TREES:
            result = self._search_tree(tree, prior_question, prior_answer)
            if result:
                return result

        return None

    def _search_tree(
        self,
        node: QuestionNode,
        target_question: str,
        wrong_answer: str,
    ) -> QuestionNode | None:
        """Recursively search for a follow-up in a question tree."""
        # Check if this node matches the question we're looking for
        if node.question.question_text == target_question:
            # Return the followup for the wrong answer if it exists
            return node.followups.get(wrong_answer)

        # Recursively search followups
        for followup in node.followups.values():
            result = self._search_tree(followup, target_question, wrong_answer)
            if result:
                return result

        return None

    def _get_generic_question(self) -> Question:
        """Get a generic fallback question."""
        available = [t for t in self.GENERIC_TREES
                    if t.question.question_text not in self._used_questions]
        if not available:
            self._used_questions.clear()
            available = self.GENERIC_TREES

        node = random.choice(available)
        self._used_questions.add(node.question.question_text)
        return node.question

    def verify_question(self, question: Question) -> Review:
        """Mock verification - always returns valid."""
        return Review(valid=True, correct_answer=question.correct_answer)


# Singleton instance
_mock_generator: MockGenerator | None = None


def get_mock_generator() -> MockGenerator:
    """Get the mock generator singleton."""
    global _mock_generator
    if _mock_generator is None:
        _mock_generator = MockGenerator()
    return _mock_generator

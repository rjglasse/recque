import os
import sys
import random
import textwrap
import string
import logging
import threading
import time

from pydantic import BaseModel

from openai import OpenAI

# AI Stuff
client = OpenAI()
key = os.getenv("OPENAI_API_KEY")
default_model = "gpt-4o-mini"
current_model = sys.argv[1] if len(sys.argv) > 1 else default_model

# List of valid models
valid_models = ["gpt-4o", "gpt-4o-mini", "o3-mini"]

if current_model not in valid_models:
    print(f"Invalid model name: {current_model}. Using default model: {default_model}")
    current_model = default_model

# Colors for terminal text
RED = '\033[31m'
GREEN = '\033[32m'
MAGENTA = '\033[35m'
RESET = '\033[0m'

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format="{asctime} - {levelname} - {message}\n", 
                    style="{", 
                    datefmt="%Y-%m-%d %H:%M",
                    filename="api_calls.log",
                    encoding="utf-8",
                    filemode="a",)
logging.info("Starting recque.py")

# Handling text wrapping for terminal display
def wrap_text(text, width=80):
    wrapped = textwrap.fill(text, width=width)
    return wrapped

# Data classes for structured output from API calls
class SkillMap(BaseModel):
    skills: list[str]

class Question(BaseModel):
    question_text: str
    correct_answer: str
    incorrect_answers: list[str]

class Review(BaseModel):
    valid: bool
    correct_answer: str

prompt_rules = """Keep the question under 100 words.
    Provide at least two incorrect but plausible and realistic alternative answers.
    The alternative answers ideally should target common misconceptions. 
    Each answer should be no more than 20 words.
    Ensure there is exactly one correct answer, verify that it is correct.
    Ensure it is not obvious which answer is correct; in terms of being longer or containing more information.
    Do not provide a prefix for the index of each alternative answer, such as a number, letter, dash or other characters.
    """

# Generate a question based on a skill (with optional prior question and answer)
def generate_question(skill, prior_question=None, prior_answer=None, variation_question=False):
    # construct prompt
    if variation_question:
        prompt = f"""Task:
            Generate a new question about {skill} that is a more challenging variation of the previous question.
            They answered this correctly: {prior_question}.
            
            Make sure you follow these rules: {prompt_rules}
            """
    elif prior_question:
        prompt = f"""Task:
            Generate a much simpler question about {skill} based on the question that was incorrectly answered: {prior_question}. 
            The learner answered: {prior_answer}. This was incorrect and shows they do not understand all the concepts.
            Try use their misconception and formulate a new related question to help explain the misconception. 
            Try to break down the original question into smaller parts that help simplify it.
            
            Make sure you follow these rules: {prompt_rules}
            """
    else:
        prompt = f"""Task:
            Create an engaging, insightful and challenging multiple choice question that focuses on this skill: {skill}.
            
            Make sure you follow these rules: {prompt_rules}
            """
    # Call chat completion endpoint
    try:
        completion = client.beta.chat.completions.parse(
            model = current_model,            
            messages = [
                {
                    "role": "user",
                    "content": f"{prompt}"
                }
            ],
            response_format = Question,
        )

        # Exract JSON string from completion
        question = completion.choices[0].message.parsed
        logging.info(question)
        # verify_question(question)
        return question

    except Exception as e:
        logging.error(f"Error: {e}")
        print(f"{RED}Error: {e}{RESET}")
        sys.exit()

# Verify that the question is valid
def verify_question(question):    
    prompt = f"""Task:
        You are given a multiple-choice question, along with possible answers.
        Your goal is to determine if at least one of the provided answers is correct.

        Question:
        {question.question_text}

        Possible Answers:
        {question.incorrect_answers} and {question.correct_answer}

        Instructions:
        - Solve the given question step by step, showing the intermediate steps if necessary.
        - Determine the correct answer.
        - Check if the correct answer matches one of the possible answers.
        - If the correct answer is not among the possible answers, provide the correct answer.
    """
    try:
        completion = client.beta.chat.completions.parse(
            model=current_model,
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt}"
                }
            ],
            response_format=Review,
        )

        # Exract JSON string from completion
        review = completion.choices[0].message.parsed
        logging.info(review)
        # Repair question if no correct answer found
        if not review.valid:
            logging.warning(f"Question had no correct answer; repairing question.")
            question.correct_answer = review.correct_answer
    except Exception as e:
        logging.error(f"Error: {e}")
        print(f"{RED}Error: {e}{RESET}")
        sys.exit()

#  Get answers with shuffled order
def shuffle_answers(question):
    answers = [question.correct_answer] + question.incorrect_answers
    random.shuffle(answers)
    return answers

# Judge answer for question
def judge(question, response):
    return question.correct_answer == response

# Generate a skillmap for a topic
def generate_skillmap(topic="basic math"):
    # construct prompt
    prompt = f"""Task:
        Generate a list of skills for the topic: {topic}. 

        Instructions:
        The list of skills should contain 3 concepts in a natural progression that are important to understand the topic.
        The response should only be the skills and no other additional information.
        There is no need to provide an index of skill, such as a number, dash or other characters."""

    # Call chat completion endpoint
    try:
        completion = client.beta.chat.completions.parse(
            model=current_model,
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt}"
                }
            ],
            response_format=SkillMap,
        )

        # Exract list of skills from completion
        skillmap = completion.choices[0].message.parsed
        logging.info(skillmap)
        return skillmap.skills
    except Exception as e:
        logging.error(f"Error: {e}")
        print(f"{RED}Error: {e}{RESET}")
        sys.exit()

# Cache for prefetched questions
prefetch_cache = {}

def prefetch_questions(topic, skill, current_question):
    """
    Prefetches simpler questions for each incorrect answer in parallel.

    Args:
        topic (str): The topic of the questions.
        skill (str): The skill being tested.
        current_question (Question): The current question being displayed.

    Returns:
        dict: A dictionary mapping incorrect answers to their prefetched simpler questions.
    """
    prefetched_questions = {}
    threads = []

    def generate_and_store(answer):
        """Generates a simpler question for a given incorrect answer and stores it."""
        if answer in prefetch_cache:
            simpler_question = prefetch_cache[answer]
        else:
            simpler_question = generate_question(topic + ". " + skill, current_question.question_text, answer)
            prefetch_cache[answer] = simpler_question
        prefetched_questions[answer] = simpler_question

    # Create a thread for each incorrect answer
    for answer in current_question.incorrect_answers:
        thread = threading.Thread(target=generate_and_store, args=(answer,))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    return prefetched_questions

def typewriter_print(text, delay=0.03):
    for char in text:
        print(char, end="", flush=True)
        time.sleep(delay)
    print()  # Add a newline at the end

def main():
    topic = input(f"{MAGENTA}Enter a topic: {RESET}").strip()
    if not topic:
        topic = "order of evaluation in maths"

    skillmap = generate_skillmap(topic)

    for skill in skillmap:
        # Pick skill and generate initial question
        print(f"\n{MAGENTA}# {string.capwords(skill)}{RESET}")
        original_question = generate_question(topic + ". " + skill)

        # Initialize stack
        miscon_stack = []
        miscon_stack.append(original_question)

        while miscon_stack:
            # Display the current question in the stack
            current_question = miscon_stack[-1]
            print()
            typewriter_print(wrap_text(f"{MAGENTA}Question{RESET}: {current_question.question_text}"))
            print()
            
            # Display answers
            answers = shuffle_answers(current_question)
            for i in range(len(answers)):
                typewriter_print(wrap_text(f"{MAGENTA}({i+1}){RESET} {answers[i]}") + "\n")

            # Get response
            while True:
                try:
                    print(f"{MAGENTA}Enter a number: {RESET}", end="")
                    
                    # Prefetch questions for incorrect answers
                    if current_question.question_text not in prefetch_cache:
                        prefetched_questions = prefetch_questions(topic, skill, current_question)
                        prefetch_cache[current_question.question_text] = prefetched_questions
                    else:
                        prefetched_questions = prefetch_cache[current_question.question_text]

                    response = int(input().strip())
                    
                    if response == 0:
                        print(f"\n{MAGENTA}Goodbye and have a nice day!{RESET}\n")
                        sys.exit()
                    if 1 <= response <= len(answers):
                        break
                    else:
                        print(f"{RED}Please enter a number between 1 and {len(answers)}.{RESET}")
                except ValueError:
                    print(f"{RED}Invalid input. Please enter a number.{RESET}")

            # Judge the response
            if judge(current_question, answers[response-1]):
                print(f"\n{GREEN}Correct! :){RESET}")
                miscon_stack.pop()  # Remove the question from the stack

                if miscon_stack:
                    print(f"{GREEN}>> Let's go back to the earlier question.{RESET}")
                else:
                    print(f"{GREEN}Well done, you've answered the question!\n{RESET}")

                    # Get user input on what to do next, another question, or next skill
                    while True:
                        next_action = input(f"{MAGENTA}Do you want to (1) answer another question, (2) move on to the next skill, or (0) exit?: {RESET}").strip().lower()
                        if next_action == "1":
                            print(f"\n{MAGENTA}# {string.capwords(skill)}{RESET}")
                            next_question = generate_question(topic + ". " + skill, variation_question=True)
                            miscon_stack.append(next_question)
                            break
                        elif next_action == "2":
                            break
                        elif next_action == "0":
                            print(f"\n{MAGENTA}Goodbye and have a nice day!{RESET}\n")
                            sys.exit()          
                        else:
                            print(f"{RED}Please enter '1', '2' or '3'.{RESET}")
            else:
                print(f"\n{RED}That's incorrect :|{RESET}")

                # Generate a simpler question
                print(f"{RED}>> Let's try another question.{RESET}")
                simpler_question = prefetched_questions[answers[response-1]]
                miscon_stack.append(simpler_question)
                
                # Mark incorrect choice with read text for current_question
                to_mark = current_question.incorrect_answers.index(answers[response-1])
                current_question.incorrect_answers[to_mark] = f"{RED}{current_question.incorrect_answers[to_mark]} (incorrect){RESET}"
    print(f"\n{MAGENTA}Congratulations, all skills covered! Goodbye and have a nice day!{RESET}\n")

if __name__ == "__main__":
    main()

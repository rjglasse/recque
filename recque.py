import os
import sys
import random
import json
import textwrap
import string
import logging

from pydantic import BaseModel

from openai import OpenAI

# AI Stuff
client = OpenAI()
key = os.getenv("OPENAI_API_KEY")

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
def wrap_text(text, width=120):
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

# Generate a question based on a skill (with optional prior question and answer)
def generate_question(skill, prior_question=None, prior_answer=None, variation_question=False):
    # construct prompt
    if variation_question:
        prompt = f"""Task:
            Generate a new question about {skill} that is a more challenging variation of the previous question so they can get more practice: {prior_question}.
            It should be indepth, contain multiple concepts and use examples to test the learner's understanding of the skill.
            Ensure there is exactly one correct answer, verify that it is correct.
            Provide at least two incorrect but plausible and realistic alternative answers.
            There is no need to provide an index of answer, such as a number, letter, dash or other characters.
            """
    elif prior_question:
        prompt = f"""Task:
            Generate a simpler question about {skill} based on the question: {prior_question}. 
            The learner answered: {prior_answer}. This was incorrect and shows they do not understand all the concepts.
            Try to isolate the misconception based on the {prior_answer} and formulate a new question to help explain the misconception. 
            Feel free to use rich examples and illustrative metaphors to help the learner understand.
            
            Instructions:
            """
    else:
        prompt = f"""Task:
            Create an engaging, insightful and challenging multiple choice question that focuses on this skill: {skill}.
            Ensure there is exactly one correct answer, verify that it is correct.
            Provide at least two incorrect but plausible and realistic alternative answers.
            There is no need to provide an index of answer, such as a number, letter, dash or other characters.
            """
    # Call chat completion endpoint
    try:
        completion = client.beta.chat.completions.parse(
            model = "gpt-4o",
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
        verify_question(question)
        return question

    except Exception as e:
        logging.error(f"Error: {e}")
        print(f"{RED}Error: {e}{RESET}")
        sys.exit()

# Verify that the question is valid
def verify_question(question):    
    prompt = f"""Task:
        You are given a multiple-choice question, along with possible answers. Your goal is to determine if at least one of the provided answers is correct.

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
            model="gpt-4o",
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
            model="gpt-4o-mini",
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

def main():
    # Establish topic from user and generate skillmap
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
            print(wrap_text(f"{MAGENTA}Question{RESET}: {current_question.question_text}"), "\n")
            
            # Display answers
            answers = shuffle_answers(current_question)
            for i in range(len(answers)):
                print(f"{MAGENTA}({i+1}){RESET} {answers[i]}")

            # Get response
            while True:
                try:
                    response = int(input(f"\n{MAGENTA}Enter a number: {RESET}").strip())
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
                        next_action = input(f"{MAGENTA}Do you want to (1) answer another question, (2) move on to the next skill, or (3) exit?: {RESET}").strip().lower()
                        if next_action == "1":
                            print(f"\n{MAGENTA}# {string.capwords(skill)}{RESET}")
                            next_question = generate_question(skill, variation_question=True)
                            miscon_stack.append(next_question)
                            break
                        elif next_action == "2":
                            break
                        elif next_action == "3":
                            print(f"\n{MAGENTA}Goodbye and have a nice day!{RESET}\n")
                            sys.exit()          
                        else:
                            print(f"{RED}Please enter '1', '2' or '3'.{RESET}")
            else:
                print(f"\n{RED}That's incorrect :|{RESET}")

                # Mark incorrect choice with read text for current_question
                to_mark = current_question.incorrect_answers.index(answers[response-1])            
                current_question.incorrect_answers[to_mark] = f"{RED}{current_question.incorrect_answers[to_mark]} (incorrect){RESET}"

                # Generate a simpler question
                simpler_question = generate_question(skill, current_question.question_text, answers[response-1])
                print(f"{RED}>> Let's try another question.{RESET}")
                miscon_stack.append(simpler_question)
    print(f"\n{MAGENTA}Congratulations, all skills covered! Goodbye and have a nice day!{RESET}\n")

if __name__ == "__main__":
    main()

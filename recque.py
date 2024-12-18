import os
import sys
import random
import json
import textwrap
import string
import logging

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

# Common prompts for generating questions
good_question = """The question should be multiple choice. 
    There should be only one correct answer.
    Each answer should be unique and plausible. 
    Do not include the answer alternative numeric index like 1), or letter like A) of the answer in the question."""

good_format = """The question should be formated for a text-based 
    terminal interface with appropriate indentation and newline characters."""

good_response = """The response should be formatted as a JSON object with three fields: 
    question_text, correct_answer, and incorrect_answers. 
    The question_text field should not contain any answer alternatives, just the question stem. 
    The correct_answer field should be a string. 
    The incorrect_answers field should be a list of strings."""

# Generate a question based on a skill (with optional prior question and answer)
def generate_question(skill, prior_question=None, prior_answer=None, variation_question=False):
    # construct prompt
    if variation_question:
        prompt = f"""Task:
            Generate a new question about {skill} that is a good variation of the previous question so they can get more practice: {prior_question}.
            It should be indepth, contain multiple concepts and use examples to test the learner's understanding of the skill.
            
            Instructions:
            """
        prompt += good_question + good_format + good_response
    elif prior_question:
        prompt = f"""Task:
            Generate a simpler question about {skill} based on the question: {prior_question}. 
            The learner answered: {prior_answer}. This was incorrect and shows they do not understand all the concepts.
            Try to isolate the misconception based on the {prior_answer} and formulate a new question to help explain the misconception. 
            Feel free to use rich examples and illustrative metaphors to help the learner understand.
            
            Instructions:
            """
        prompt += good_question + good_format + good_response
    else:
        prompt = f"""Task:
            Create an insightful and challenging multiple choice question in JSON format focused on this skill: {skill}. 
            
            Ensure there is exactly one correct answer, verify that is is correct.
            Provide at least two incorrect but plausible answers. 
            
            The JSON object should have three fields:
            question_text: A single question.
            correct_answer: A single string with the correct answer to the question.
            incorrect_answers: An array of strings for the incorrect answers.
            
            Respond only with the JSON object and no additional commentary.
            """
        # prompt += good_question + good_format + good_response
    
    # Call chat completion endpoint
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt}"
                }
            ]
        )

        # Exract JSON string from completion
        json_string = completion.choices[0].message.content.strip().strip("```json").strip("```")
        logging.info(json_string)
        response = json.loads(json_string)

        # Build response dictionary
        question_text = response["question_text"]
        correct_answer = response["correct_answer"]
        incorrect_answers = response["incorrect_answers"]
        
        # Check if the question is valid
        verify_question(response)

    except Exception as e:
        logging.error(f"Error: {e}")
        print(f"{RED}Error: {e}{RESET}")
        sys.exit()

    return {"question_text": question_text, "correct_answer": correct_answer, "incorrect_answers": incorrect_answers}

# Verify that the question is valid
def verify_question(question):    
    prompt = f"""Task:
        You are given a multiple-choice question, along with possible answers. Your goal is to determine if at least one of the provided answers is correct.

        {question["question_text"]}

        Possible Answers:
        {question["incorrect_answers"]} and {question["correct_answer"]}

        Instructions:
        Solve the given question step by step, showing the intermediate steps if necessary.
        Determine the correct answer.
        Check if the correct answer matches one of the possible answers.

        Response:
        Return a JSON object with the following fields:
        valid: true if the correct answer is found among the possible answers; otherwise, false.
        correct_answer: A string containing the correct answer.
        Only return the JSON object and no additional commentary.
    """
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt}"
                }
            ]
        )

        # Exract JSON string from completion
        json_string = completion.choices[0].message.content.strip().strip("```json").strip("```")
        logging.info(json_string)
        response = json.loads(json_string)
        # Repair question if no correct answer
        if not response["valid"]:
            logging.WARNING(f"Question had no correct answer; repairing question.")
            question['correct_answer'] = response["correct_answer"]
    except Exception as e:
        logging.error(f"Error: {e}")
        print(f"{RED}Error: {e}{RESET}")
        sys.exit()

#  Get answers with shuffled order
def shuffle_answers(current_question):
    answers = [current_question["correct_answer"]] + current_question["incorrect_answers"]
    random.shuffle(answers)
    return answers

# Judge answer for question
def judge(question, response):
    return question["correct_answer"] == response

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
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt}"
                }
            ]
        )

        # Exract JSON string from completion
        json_string = completion.choices[0].message.content.strip().strip("```json").strip("```")
        logging.info(json_string)
    except Exception as e:
        logging.error(f"Error: {e}")
        print(f"{RED}Error: {e}{RESET}")
        sys.exit()
    skillmap = json_string.split("\n")
    return skillmap

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
            print(wrap_text(f"{MAGENTA}Question{RESET}: {current_question["question_text"]}"), "\n")
            
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
                            next_question = generate_question(topic + ". " + skill, current_question, variation_question=True)
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
                to_mark = current_question["incorrect_answers"].index(answers[response-1])            
                current_question["incorrect_answers"][to_mark] = f"{RED}{current_question["incorrect_answers"][to_mark]} (incorrect){RESET}"

                # Generate a simpler question
                simpler_question = generate_question(skill, current_question["question_text"], answers[response-1])
                print(f"{RED}>> Let's try another question.{RESET}")
                miscon_stack.append(simpler_question)

if __name__ == "__main__":
    main()

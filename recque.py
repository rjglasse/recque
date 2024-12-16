import random
import os
import sys
import json
import textwrap
import string
from openai import OpenAI

# AI Stuff
client = OpenAI()
key = os.getenv("OPENAI_API_KEY")

# Colors for terminal text
RED = '\033[31m'
GREEN = '\033[32m'
MAGENTA = '\033[35m'
RESET = '\033[0m'

# Handling text wrapping for terminal display
def wrap_text(text, width=120):
    wrapped = textwrap.fill(text, width=width)
    return wrapped

# Common prompts for generating questions
good_question = """The question should be multiple choice. There should be one correct answer.
    Ideally there should be three or more answers, but if the question is binary in nature, then two answers is ok. 
    Each answer should be unique and plausible. 
    Do not include the answer alternative numeric index like 1), or letter like A) of the answer in the question.
    The question should be relevant and focused on the skill being tested."""

good_format = """The question should be formated for a text-based 
    terminal interface with appropriate tabs and newline characters."""

good_response = """The question should be formatted as a JSON object with three fields: 
    question_text, correct_answer, and incorrect_answers. 
    The question_text field should not contain any answer alternatives, just the question stem. 
    The correct_answer field should be a string. 
    The incorrect_answers field should be a list of strings."""

# Generate a question based on a skill (with optional prior question and answer)
def generate_question(skill, prior_question=None, prior_answer=None, variation_question=False):
    # construct prompt
    if variation_question:
        prompt = f"""Generate a new question about {skill} that is a good variation of the previous question so they can get more practice: {prior_question}.
            It should be indepth, contain multiple concepts and use examples to test the learner's understanding of the skill."""
        prompt += good_question + good_format + good_response
    elif prior_question:
        prompt = f"""Generate a simpler question about {skill} based on the question: {prior_question}. 
            The learner answered: {prior_answer}. This was incorrect and shows they do not understand all the concepts.
            Try to isolate the misconception based on the {prior_answer} and formulate a new question to help explain the misconception. 
            Feel free to use rich examples and illustrative metaphors to help the learner understand."""
        prompt += good_question + good_format + good_response
    else:
        prompt = f"""Generate a question about {skill}. 
            It should be indepth, contain multiple concepts and use examples to test the learner's understanding of the skill."""
        prompt += good_question + good_format + good_response
    
    # Call chat completion endpoint
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system",
            "content": "You are a socratic teacher who only creates excellently pedagogical questions and never provides explanations."
            },
            {
                "role": "user",
                "content": f"{prompt}"
            }
        ]
    )

    # Exract JSON string from completion
    json_string = completion.choices[0].message.content.strip().strip("```json").strip("```")
    response = json.loads(json_string)

    # Build response dictionary
    question_text = response["question_text"]
    correct_answer = response["correct_answer"]
    incorrect_answers = response["incorrect_answers"]

    # TODO: verify that the correct answer is the correct answer, otherwise re-prompt for a new question 3 times

    return {"question_text": question_text, "correct_answer": correct_answer, "incorrect_answers": incorrect_answers}

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
    prompt = f"""Generate a list of skills for the topic: {topic}. 
        The list of skills should contain 3 concepts in a natural progression that are important to understand the topic.
        The response should only be the skills and no other additional information.
        There is no need to provide an index of skill, such as a number, dash or other characters."""

    # Call chat completion endpoint
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system",
            "content": f"You are a subject expert in {topic}."
            },
            {
                "role": "user",
                "content": f"{prompt}"
            }
        ]
    )

    # Exract JSON string from completion
    json_string = completion.choices[0].message.content.strip().strip("```json").strip("```")
    # response = json.loads(json_string)

    skillmap = json_string.split("\n")
    return skillmap

def main():
    # Establish topic and generate skillmap
    topic = sys.argv[1] if len(sys.argv) > 1 else "order of evaluation in maths"
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
                            print(f"\n{MAGENTA}{skill}{RESET}")
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
                simpler_question = generate_question(skill, current_question, answers[response-1])
                print(f"{RED}>> Let's try another question.{RESET}")
                miscon_stack.append(simpler_question)

if __name__ == "__main__":
    main()

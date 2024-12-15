import random
from openai import OpenAI
import os
import json

# AI Stuff
client = OpenAI()
key = os.getenv("OPENAI_API_KEY")

# Colors for terminal text
RED = '\033[31m'
GREEN = '\033[32m'
MAGENTA = '\033[35m'
RESET = '\033[0m' # called to return to standard terminal text color

good_question = """The question should be multiple choice.
    There should be one correct answer.
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

def generate_question(skill, prior_question=None, prior_answer=None):
    # construct prompt
    if prior_question:
        prompt = f"""Generate a simpler question about {skill} based on the question: {prior_question}. 
            The learner answered: {prior_answer}. This was incorrect and shows they do not understand all the concepts.
            Try to isolate the misconception based on the {prior_answer} and formulate a new question to help explain the misconception. 
            Feel free to use rich examples and illustrative metaphors to help the learner understand."""
        prompt += good_question + good_format + good_response
    else:
        prompt = f"""Generate a question about {skill}. 
            It should be indepth, contain multiple concepts and use examples to test the learner's understanding of the skill."""
        prompt += good_question + good_format + good_response
    
    # call chat completion
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

    # build response
    question_text = response["question_text"]
    correct_answer = response["correct_answer"]
    incorrect_answers = response["incorrect_answers"]
    return {"question_text": question_text, "correct_answer": correct_answer, "incorrect_answers": incorrect_answers}

#  Get answers with shuffled order
def shuffle_answers(current_question):
    answers = [current_question["correct_answer"]] + current_question["incorrect_answers"]
    random.shuffle(answers)
    return answers

# Judge answer for question
def judge(question, response):
    return question["correct_answer"] == response

def main():
    # Static skill and initial question
    skill = "order of evaluation for addition, subtraction and multiplication"
    original_question = generate_question(skill)

    # Initialize stack
    miscon_stack = []
    miscon_stack.append(original_question)

    while miscon_stack:
        # Display the current question in the stack
        current_question = miscon_stack[-1]
        print(f"\n{MAGENTA}Question{RESET}: {current_question["question_text"]}\n")
        
        # Display answers
        answers = shuffle_answers(current_question)
        for i in range(len(answers)):
            print(f"{MAGENTA}({i+1}){RESET} {answers[i]}")

        # Get response
        while True:
            try:
                response = int(input("\nEnter a number: ").strip())
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
                print(">> Let's go back to the earlier question.")
            else:
                print("Well done, you've completed all questions!\n")
        else:
            print(f"\n{RED}That's incorrect :|{RESET}")
            # Mark incorrect choice with read text for current_question
            to_mark = current_question["incorrect_answers"].index(answers[response-1])            
            current_question["incorrect_answers"][to_mark] = f"{RED}{current_question["incorrect_answers"][to_mark]} (incorrect){RESET}"


            # Generate a simpler question
            simpler_question = generate_question(skill, current_question, answers[response-1])
            print(">> Let's try another question.")
            miscon_stack.append(simpler_question)

if __name__ == "__main__":
    main()

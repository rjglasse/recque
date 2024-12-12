import random
from openai import OpenAI
import os
import json

client = OpenAI()
key = os.getenv("OPENAI_API_KEY")

good_question = """The question should be multiple choice. 
    There should only be one correct answer. 
    Each answer should be unique and plausible. 
    The question should be clear and concise. 
    The question should be relevant to the skill being tested. 
    Ideally there should be three answers, but if the question is essentuially binary in nature, then two answers is allowed. 
    Do not include the index like 1, or letter like A) of the answer."""

good_format = """The question should be in the form of a string formmated for a text-based 
    terminal interface with appropriate tabs and newline characters to give nice formatting. 
    The correct answer should be in the form of a string. 
    The incorrect answers should be in the form of a list of strings."""

good_response = """The question should be formatted as a JSON object with three fields: 
    question_text, correct_answer, and incorrect_answers. 
    The question_text field should be a string and should not contain any answers, just the question stem. 
    The correct_answer field should be a string. 
    The incorrect_answers field should be a list of strings."""

def generate_question(skill, prior_question=None, prior_answer=None):
    # construct prompt
    if prior_question:
        prompt = f"Generate a simpler question about {skill} based on the question: {prior_question}. The learner answered: {prior_answer}. This was incorrect and shows they do not understand all the concepts. Try to isolate the misconception and formulate a simpler question to explain the misconception."
        prompt += good_question + good_format + good_response
    else:
        prompt = f"Generate a question about {skill}."
        prompt += good_question + good_format + good_response
    
    # call chat completion
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system",
            "content": "You are a helpful teacher that likes to make questions for students, but never explain, only give simpler questions."
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
    skill = "Moby Dick and its themes"
    original_question = generate_question(skill)

    # Initialize stack
    miscon_stack = []
    miscon_stack.append(original_question)

    while miscon_stack:
        # Display the current question in the stack
        current_question = miscon_stack[-1]
        print(f"Question: {current_question["question_text"]}")
        
        # Display answers
        answers = shuffle_answers(current_question)
        for i in range(len(answers)):
            print(f"({i+1}) {answers[i]}")

        # Get response
        while True:
            try:
                response = int(input("Enter a number: ").strip())
                if 1 <= response <= len(answers):
                    break
                else:
                    print(f"Please enter a number between 1 and {len(answers)}.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        # Judge the response
        if judge(current_question, answers[response-1]):
            print("Correct!")
            miscon_stack.pop()  # Remove the question from the stack

            if miscon_stack:
                print("Let's go back to the earlier question.\n")
            else:
                print("Well done, you've completed all questions!")
        else:
            print("That's incorrect.")

            # Generate a simpler question
            simpler_question = generate_question(skill, current_question, answers[response-1])
            print("Let's simplify the question.\n")
            miscon_stack.append(simpler_question)

if __name__ == "__main__":
    main()

import os
import random
import logging
from flask import Flask, render_template, request, jsonify, session
from pydantic import BaseModel
from openai import OpenAI

# Set up Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management

# AI Stuff
client = OpenAI()
key = os.getenv("OPENAI_API_KEY")
default_model = "gpt-4o-mini"
current_model = os.getenv("OPENAI_MODEL", default_model)

# List of valid models
valid_models = ["gpt-4o", "gpt-4o-mini", "o3-mini"]

if current_model not in valid_models:
    print(f"Invalid model name: {current_model}. Using default model: {default_model}")
    current_model = default_model

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format="{asctime} - {levelname} - {message}\n", 
                    style="{", 
                    datefmt="%Y-%m-%d %H:%M",
                    filename="api_calls.log",
                    encoding="utf-8",
                    filemode="a",)
logging.info("Starting recque_web.py")

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

prompt_rules = """Keep the question under 50 words.
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
            Generate a simpler question about {skill} based on the question that was incorrectly answered: {prior_question}. 
            The learner answered: {prior_answer}. This was incorrect and shows they do not understand all the concepts.
            Try use their misconception and formulate a new related question to help explain the misconception. 
            Perhaps try to break down the original question into smaller parts that help simplify it.
            
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

        # Extract JSON string from completion
        question = completion.choices[0].message.parsed
        logging.info(question)
        return question

    except Exception as e:
        logging.error(f"Error: {e}")
        return None

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

        # Extract list of skills from completion
        skillmap = completion.choices[0].message.parsed
        logging.info(skillmap)
        return skillmap.skills
    except Exception as e:
        logging.error(f"Error: {e}")
        return ["Basic concepts", "Intermediate concepts", "Advanced concepts"]

# Generate a simpler question for specific answer
def generate_simpler_question(topic, skill, current_question, selected_answer):
    try:
        simpler_question = generate_question(topic + ". " + skill, current_question, selected_answer)
        return simpler_question
    except Exception as e:
        logging.error(f"Error generating simpler question: {e}")
        return None

# Flask routes
@app.route('/')
def index():
    # Reset session when returning to homepage
    session.clear()
    return render_template('index.html')

@app.route('/start_quiz', methods=['POST'])
def start_quiz():
    topic = request.form.get('topic', 'basic math')
    
    # Generate skillmap for the topic
    skills = generate_skillmap(topic)
    
    # Store in session
    session['topic'] = topic
    session['skills'] = skills
    session['current_skill_index'] = 0
    session['question_stack'] = []
    
    return jsonify({'redirect': '/quiz'})

@app.route('/quiz')
def quiz():
    if 'topic' not in session:
        return jsonify({'redirect': '/'})
    
    return render_template('quiz.html', 
                          topic=session['topic'],
                          skill=session['skills'][session['current_skill_index']])

@app.route('/get_question')
def get_question():
    if not session.get('question_stack'):
        # Generate initial question for current skill
        skill = session['skills'][session['current_skill_index']]
        question = generate_question(session['topic'] + ". " + skill)
        session['question_stack'] = [question.dict()]
    
    # Get current question
    current_question = session['question_stack'][-1]
    
    # Shuffle answers
    answers = [current_question['correct_answer']] + current_question['incorrect_answers']
    random.shuffle(answers)
    
    return jsonify({
        'question_text': current_question['question_text'],
        'answers': answers,
        'skill': session['skills'][session['current_skill_index']]
    })

@app.route('/check_answer', methods=['POST'])
def check_answer():
    selected_answer = request.form.get('answer')
    current_question = session['question_stack'][-1]
    
    is_correct = selected_answer == current_question['correct_answer']
    
    if is_correct:
        # Remove from stack if correct
        session['question_stack'].pop()
        session.modified = True
        
        if not session['question_stack']:
            return jsonify({
                'correct': True,
                'stack_empty': True,
                'message': 'Correct! Well done!'
            })
        else:
            return jsonify({
                'correct': True,
                'stack_empty': False,
                'message': 'Correct! Going back to the previous question.'
            })
    else:
        # Generate simpler question
        skill = session['skills'][session['current_skill_index']]
        simpler_question = generate_simpler_question(
            session['topic'], 
            skill, 
            current_question['question_text'], 
            selected_answer
        )
        
        if simpler_question:
            session['question_stack'].append(simpler_question.dict())
            session.modified = True
            
        return jsonify({
            'correct': False,
            'message': 'Incorrect. Let\'s try a simpler question.'
        })

@app.route('/next_action', methods=['POST'])
def next_action():
    action = request.form.get('action')
    
    if action == 'next_skill':
        # Move to next skill
        session['current_skill_index'] += 1
        session['question_stack'] = []
        
        if session['current_skill_index'] >= len(session['skills']):
            return jsonify({
                'complete': True,
                'message': 'Congratulations! You\'ve completed all skills!'
            })
        else:
            return jsonify({
                'next_skill': True,
                'skill': session['skills'][session['current_skill_index']]
            })
    
    elif action == 'new_question':
        # Generate a new question for the same skill
        skill = session['skills'][session['current_skill_index']]
        variation_question = generate_question(session['topic'] + ". " + skill, variation_question=True)
        
        if variation_question:
            session['question_stack'] = [variation_question.dict()]
            session.modified = True
            
        return jsonify({
            'new_question': True
        })

if __name__ == '__main__':
    app.run(debug=True)

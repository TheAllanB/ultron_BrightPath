from flask import Flask, render_template, request, session, jsonify
from markupsafe import Markup
import google.generativeai as genai
import os
import re

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Load API key from environment
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

# Custom filter to replace newlines with <br>
@app.template_filter('nl2br')
def nl2br_filter(s):
    return Markup(s.replace('\n', '<br>'))

# Register the filter with Jinja2
app.jinja_env.filters['nl2br'] = nl2br_filter

# Home route
@app.route('/')
def home():
    return render_template('home.html')

# Quiz page route
@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    if request.method == 'POST':
        user_prompt = request.form.get('prompt', '')
        timer = int(request.form.get('timer', 30))
        difficulty = request.form.get('difficulty', 'medium')
        num_questions = int(request.form.get('num_questions', 5))

        # Create a GenerativeModel instance and generate quiz content
        model = genai.GenerativeModel('gemini-1.5-flash')

        try:
            # Improved prompt structure
            specific_details = user_prompt
            response = model.generate_content(
                f"Generate {num_questions} multiple choice questions about {specific_details}. The difficulty should be {difficulty}. Each question must have 4 options labeled A), B), C), and D), and indicate the correct answer."
            )

            # Process the response as before
            lines = response.text.strip().split('\n')
            generated_quiz = []
            current_question = None

            for line in lines:
                line = line.strip()
                question_match = re.match(r"^\*\*(\d+)\.\s*(.*?)\*\*$", line)
                if question_match:
                    current_question = {"question": question_match.group(2), "options": [], "correct_answer": None}
                    generated_quiz.append(current_question)
                elif line.startswith(("A)", "B)", "C)", "D)")):
                    if current_question is not None:
                        current_question["options"].append(line)
                        # Assuming the correct answer is the first option mentioned
                        if current_question["correct_answer"] is None:
                            current_question["correct_answer"] = line

            # Filter out invalid questions (questions without exactly 4 options)
            generated_quiz = [q for q in generated_quiz if len(q['options']) == 4]

            if not generated_quiz:
                raise Exception("No valid questions generated. Try again.")

            # Store questions in session
            session['quiz'] = generated_quiz
            session['current_question'] = 0
            session['user_answers'] = []
            session['timer'] = timer

            return render_template('quiz.html', quiz_generated=True, current_question=session['current_question'], timer=session['timer'], question=session['quiz'][0])

        except Exception as e:
            return render_template('quiz.html', quiz_generated=False, error=str(e))

    return render_template('quiz.html', quiz_generated=False)

# Submit answers and proceed to the next question
@app.route('/next_question', methods=['POST'])
def next_question():
    user_answer = request.form.get('user_answer')
    session['user_answers'].append(user_answer)
    session['current_question'] += 1

    # Check if there are more questions
    if session['current_question'] < len(session['quiz']):
        return render_template('quiz.html', quiz_generated=True, current_question=session['current_question'], timer=session['timer'], question=session['quiz'][session['current_question']])
    else:
        # Calculate score
        correct_answers = [q['correct_answer'] for q in session['quiz']]
        user_score = sum(1 for i, answer in enumerate(session['user_answers']) if answer == correct_answers[i])

        return render_template('results.html', answers=session['user_answers'], quiz=session['quiz'], score=user_score, total=len(session['quiz']))



# Utility function to format code snippets
def format_code_snippet(response_text):
    # Add line breaks and maintain appropriate spacing for code snippets
    response_text = response_text.replace("```", "<br>```").replace("```", "```<br>")
    response_text = response_text.replace("\n", "<br>")
    return response_text


@app.route('/news/load_more', methods=['GET'])
def load_more_news():
    offset = int(request.args.get('offset', 0))
    news_prompt = session.get('news_prompt', 'student news')  # Use the last used prompt

    # Generate or fetch news content
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(f"Provide the latest {news_prompt}")

    # Example of splitting response into articles
    generated_articles = response.text.split('\n\n')
    news_articles = []
    for article in generated_articles[offset:offset+5]:  # Load 5 more articles
        lines = article.split('\n')
        if len(lines) >= 2:
            news_articles.append({
                'title': lines[0],
                'description': lines[1],
                'url': '#',  # Format this URL as needed
            })

    return jsonify(news_articles=news_articles)

# News page route
@app.route('/news', methods=['GET', 'POST'])
def news_page():
    if request.method == 'POST':
        news_prompt = request.form.get('news_prompt', 'student news')
        session['news_prompt'] = news_prompt  # Store the prompt for loading more articles

        # Generate or fetch news content
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(f"Provide the latest {news_prompt}")

        # Example of splitting response into articles
        generated_articles = response.text.split('\n\n')
        news_articles = []
        for article in generated_articles:
            lines = article.split('\n')
            if len(lines) >= 2:
                news_articles.append({
                    'title': lines[0],
                    'description': lines[1],
                    'url': '#',  # Format this URL as needed
                })

        session['news_articles'] = news_articles
    else:
        news_articles = session.get('news_articles', [])

    return render_template('news.html', news_articles=news_articles)


@app.route('/review', methods=['GET', 'POST'])
def review():
    if request.method == 'POST':
        topic_prompt = request.form.get('topic_prompt', '')
        model = genai.GenerativeModel('gemini-1.5-flash')

        try:
            # Generate relevant information
            response_info = model.generate_content(f"Provide detailed information about {topic_prompt}.")
            review_info = response_info.text.strip()

            # Generate YouTube links
            response_youtube = model.generate_content(f"Generate YouTube links related to {topic_prompt}.")
            youtube_links = response_youtube.text.strip().split('\n')

            return render_template('review.html', review_generated=True, review_info=review_info, youtube_links=youtube_links)

        except Exception as e:
            return render_template('review.html', review_generated=False, error=str(e))

    return render_template('review.html', review_generated=False)

# Code page route
@app.route('/code')
def code():
    return render_template('code.html')

# Chatbot page route
@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'chat_history' not in session:
        session['chat_history'] = []

    if request.method == 'POST':
        user_message = request.form.get('user_message', '')
        if user_message:
            session['chat_history'].append({'role': 'user', 'content': user_message})

            # Call the Google AI API
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(user_message)

            # Format the assistant's response for better readability
            formatted_response = format_code_snippet(response.text)
            session['chat_history'].append({'role': 'assistant', 'content': formatted_response})

    return render_template('chat.html', chat_history=session['chat_history'])

# Clear chat history
@app.route('/clear_chat', methods=['POST'])
def clear_chat():
    session.pop('chat_history', None)  # Clear the chat history from session
    return jsonify({'message': 'Chat cleared'})  # Return a JSON response to indicate success

if __name__ == '__main__':
    app.run(debug=True)

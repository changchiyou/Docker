import os
import time
from functools import wraps
from flask import Flask, abort, jsonify, request, send_from_directory
from flask_cors import CORS

from utils.gpt_generate import chat_development
from utils.text_pp import create_ppt, parse_response

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
CORS(app)

def require_secret_key(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if auth_header != f"Bearer {app.config['SECRET_KEY']}":
            return jsonify({"message": "Unauthorized"}), 401
        return func(*args, **kwargs)
    return wrapper

@app.route("/generator", methods=["POST"])
@require_secret_key
def generate():
    number_of_slide = request.form.get("number_of_slide")
    user_text = request.form.get("user_text")
    presentation_title = request.form.get("presentation_title")
    presenter_name = request.form.get("presenter_name")
    insert_image = request.form.get("insert_image", False)
    template_choice = request.form.get(
        "template_choice", "simple"
    )
    filename = request.form.get("filename", f"{str(int(time.time() * 1000))}")

    # Check if any of the required fields are missing
    if not any([number_of_slide, user_text, presentation_title, presenter_name]):
        return jsonify({"status": "error", "message": "Missing required fields!"}), 400

    user_message = (
        f"I want you to come up with the idea for the PowerPoint with zh-tw. The number of slides is {number_of_slide if number_of_slide != '-1' else 'unrestricted'}. "
        f"The content is: {user_text}.The title of content for each slide must be unique, "
        f"and extract the most important keyword within two words for each slide. Summarize the content for each slide. "
    )

    assistant_response = chat_development(user_message)

    # Check the response (for debug)
    print(f"Assistant Response:\n{assistant_response}")
    slides_content = parse_response(assistant_response)
    create_ppt(
        slides_content=slides_content,
        presentation_title=presentation_title,
        presenter_name=presenter_name,
        insert_image=insert_image,
        template_choice=template_choice,
        filename=filename,
    )

    return jsonify(
        {"status": "success", "message": "Presentation generated successfully!"}
    )


@app.route("/download/<filename>", methods=["GET"])
def download_file(filename):
    try:
        return send_from_directory("generated", filename, as_attachment=True)

    except FileNotFoundError:
        abort(404)

@app.route("/file_size/<filename>", methods=["GET"])
def get_file_size(filename):
    current_dir = os.path.abspath(os.path.dirname(__file__))
    file_path = os.path.join(current_dir, "generated", filename)
    if os.path.exists(file_path):
        file_size = os.path.getsize(file_path)
        return jsonify({"filename": filename, "size_in_bytes": file_size}), 200
    else:
        return jsonify({"message": "File not found!"}), 404

if __name__ == "__main__":
    app.run(
        port=int(os.getenv("PORT", 5001)), 
        debug=bool(os.getenv("DEBUG", True)),
        host="0.0.0.0",
    )

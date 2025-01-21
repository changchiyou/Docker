import os

import openai
from openai import OpenAI

client = OpenAI(api_key=os.getenv("LITELLM_API_KEY"), base_url="http://litellm-proxy:8000")


def chat_development(user_message):
    conversation = build_conversation(user_message)
    try:
        assistant_message = generate_assistant_message(conversation)
    except openai.RateLimitError:
        assistant_message = "Rate limit exceeded. Sleeping for a bit..."

    return assistant_message


def build_conversation(user_message):
    return [
        {
            "role": "system",
            "content": "You are an assistant that gives the idea for PowerPoint presentations. When answering, give the user the summarized content for each slide based on the number of slide. "
            "And the format of the answer must be Slide X(the number of the slide): {title of the content} /n Content: /n content with some bullet points."
            "Keyword: /n Give the most important keyword(within two words) that represents the slide for each one"
            "Here is the example of output:"
            """
            Slide 1: Introduction to Taiwan
            Content:
            - Brief overview of Taiwan
            - Location and culture
            Keywords: Taiwan Overview

            Slide 2: Good Places in Taiwan
            Content:
            - Scenic spots (e.g., Taroko Gorge, Sun Moon Lake)
            - Night markets and street food
            Keywords: Beautiful Destinations

            ...""",
        },
        {"role": "user", "content": user_message},
    ]


def generate_assistant_message(conversation):
    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL"), messages=conversation
    )
    return response.choices[0].message.content

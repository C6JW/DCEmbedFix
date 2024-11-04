from flask import Flask, request, request, redirect, render_template_string
#import requests
import httpx
from bs4 import BeautifulSoup
import logging
import re
from urllib.parse import parse_qs
OG_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta property="og:title" content="{{ title }}">
    <meta property="og:description" content="{{ description }}">
    <meta property="og:image" content="{{ image }}">
    <meta property="og:url" content="{{ original_url | safe }}">
    <meta http-equiv="refresh" content="1;url={{ original_url | safe }}">
    <title>{{ title }}</title>
</head>
<body>
    <p>Redirecting to the original post...</p>
    <script>
        window.location.href = "{{ original_url | safe }}";
    </script>
</body>
</html>
"""

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

def fetch_with_httpx(dcinside_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36'
    }
    try:
        with httpx.Client(verify=False, follow_redirects=True) as client:
            response = client.get(dcinside_url, headers=headers, timeout=5)
            response.raise_for_status()
        return response.text
    except httpx.RequestError as e:
        logging.error(f"Failed to retrieve the page: {e}")
        return None

@app.route('/')
def generate_embed():
    dcinside_url = request.query_string.decode('utf-8')
    if dcinside_url.startswith("url="):
        dcinside_url = dcinside_url.removeprefix("url=")
    if not dcinside_url:
        logging.error("No URL provided.")
        return "No URL provided.", 400
    logging.debug(f"Fetching URL: {dcinside_url}")

    page_content = fetch_with_httpx(dcinside_url)
    if not page_content:
        return "Failed to retrieve the page.", 500

    try:
        soup = BeautifulSoup(page_content, 'html.parser')

        title = soup.find('title').text if soup.find('title') else "No Title"
        description = soup.find('meta', {'name': 'description'})['content'] if soup.find('meta', {'name': 'description'}) else "No Description"
        image = soup.find('meta', {'property': 'og:image'})['content'] if soup.find('meta', {'property': 'og:image'}) else "https://static.wikia.nocookie.net/joke-battles/images/d/df/Gigachad.png/revision/latest/scale-to-width-down/340?cb=20230812064835"
        print(image)

        logging.debug(f"Parsed title: {title}")
        logging.debug(f"Parsed description: {description}")
        logging.debug(f"Parsed image: {image}")
    except Exception as e:
        logging.error(f"Error parsing HTML: {e}")
        return "Error parsing HTML content.", 500
    try:
        print("URL: "+ dcinside_url)
        return render_template_string(OG_TEMPLATE, title=title, description=description, image=image, original_url=dcinside_url)
    except Exception as e:
        logging.error(f"Error rendering template: {e}")
        return "Error rendering template.", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=52300)

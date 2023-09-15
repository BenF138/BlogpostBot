import openai
from fpdf import FPDF
import re
import datetime
import time
from actions.web_search import web_search
from actions.web_scrape import async_browse
from agent.research_agent import ResearchAgent




# Constants
COST_PER_1000_TOKENS = 0.03
MAX_COST = 1.0
API_KEY_PATH = 'api.key.txt'
ORGANIZATION = "org-oEDHv9O5dB5RYovDX7Imliut"

def remove_non_latin1_characters(s):
    return ''.join(i for i in s if ord(i) < 256)

def calculate_cost(tokens):
    return (tokens / 1000) * COST_PER_1000_TOKENS

def check_continue(tokens, cumulative_tokens=0):
    total_tokens = tokens + cumulative_tokens
    cost = calculate_cost(total_tokens)
    if cost > MAX_COST:
        user_input = input(f"Projected total cost is ${cost:.2f}. Continue? (yes/no): ")
        return user_input.lower() == 'yes'
    return True

def safe_api_call(model, system_message, user_message, cumulative_tokens=0, retries=3, delay=10):
    for attempt in range(retries):
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ]
            )
            tokens_used = response['usage']['total_tokens']

            print("API Response:", response.choices[0].message['content'])

            if not check_continue(tokens_used, cumulative_tokens):
                print("Stopping due to cost concerns.")
                exit()
            return response.choices[0].message['content'], tokens_used
        except openai.error.APIConnectionError:
            if attempt < retries - 1:  # i.e. not the last attempt
                print(f"Error communicating with OpenAI. Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("Max retries reached. Exiting.")
                exit()

def generate_pdf(keyword, content):
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, 'Final Draft', 0, 1, 'C')
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, 'Page ' + str(self.page_no()), 0, 0, 'C')
    
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, content)
    
    current_timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    folder_path = "articles/"  # specify your desired folder path here
    filename = f"{folder_path}{keyword}_{current_timestamp}.pdf"
    pdf.output(filename)
    return filename

async def conduct_research_on_topic(topic, keyword):
    agent = ResearchAgent(question=topic, agent="Your chosen agent", agent_role_prompt=None, websocket=None)
    research_summary = await agent.conduct_research()
    report, _ = await agent.write_report(report_type="summary")
    return report

#def main():
    openai.api_key_path = API_KEY_PATH
    openai.organization = ORGANIZATION

    initial_directive = input("Enter your prompt (title of the post): ")
    target_keyword = input("Enter your target keyword: ")

    total_tokens = 0

    # Initial draft
    draft, tokens = safe_api_call("gpt-4", 
                                  "You are a professional content writer with 10+ years of experience in the art market. Consider the following prompt and keyword and write a blogpost about it. Ensure the article is between 5000 and 8000 words long.",
                                  f"Prompt: {initial_directive}\nKeyword: {target_keyword}")
    total_tokens += tokens

    # Initial editor feedback
    editor_feedback, tokens = safe_api_call("gpt-4",
                                            f"You are an editor with 10+ years of experience. Review the following article. Checks the content for clarity, coherence, consistency, grammar, and punctuation. Give a bulleted list of feedback and advice for the content writer. ",
                                            draft, total_tokens)
    total_tokens += tokens

    # SEO feedback
    seo_feedback, tokens = safe_api_call("gpt-4",
                                         f"You are an SEO professional. Review the following article based on the keyword '{target_keyword}'. Give a bulleted list of feedback and advice for the content writer. ",
                                         draft, total_tokens)
    total_tokens += tokens

    # First rewrite based on feedback
    final_draft, tokens = safe_api_call("gpt-4",
                                        "You are a professional content writer with 10+ years of experience in the art market. Take the feedback and rewrite the article. Ensure the article is between 5000 and 8000 words long. Ensure the content is engaging and accurate.",
                                        f"Original Draft: {draft}\nEditor Feedback: {editor_feedback}\nSEO Feedback: {seo_feedback}", total_tokens)
    total_tokens += tokens

    # Senior editor feedback
    senior_editor_feedback, tokens = safe_api_call("gpt-4",
                                                   "You are a senior editor with 15+ years of experience. Review the following article. Check the content for clarity, coherence, consistency, interestingness, grammar, and punctuation. Give a bulleted list of feedback and advice for the content writer.",
                                                   final_draft, total_tokens)
    total_tokens += tokens

    # Second rewrite based on senior editor feedback
    revised_final_draft, tokens = safe_api_call("gpt-4",
                                                "You are a professional content writer with 10+ years of experience in the art market. Take the senior editor's feedback and rewrite the article. Ensure the article is between 5000 and 8000 words long. Ensure the content is engaging and accurate.",
                                                f"Original Draft: {final_draft}\nSenior Editor Feedback: {senior_editor_feedback}", total_tokens)
    total_tokens += tokens

    # Suggest a title
    suggested_title, tokens = safe_api_call("gpt-4",
                                            "You are a creative writer. Suggest a title for the article. The audience are people interested in the art market.",
                                            initial_directive, total_tokens)
    total_tokens += tokens

    # You can continue with the rest of your code here...

    cleaned_draft = re.sub(r'<.*?>', '', final_draft)
    cleaned_draft = remove_non_latin1_characters(cleaned_draft)

    filename = generate_pdf(target_keyword, cleaned_draft)
    print(f"Final draft saved as '{filename}'")

    total_cost = calculate_cost(total_tokens)
    print(f"Total cost for {total_tokens} tokens: ${total_cost:.2f}")
def main():
    openai.api_key_path = API_KEY_PATH
    openai.organization = ORGANIZATION

    initial_directive = input("Enter your prompt (title of the post): ")
    target_keyword = input("Enter your target keyword: ")

    total_tokens = 0

    # Researcher Role
    research_report = conduct_research_on_topic(initial_directive, target_keyword)
    
    print("\n=== Research Report ===\n")
    print(research_report)
    print("\n=======================\n")
     
    # Content Writer Role
    draft, tokens = safe_api_call("gpt-4", 
                                  "You are a professional content writer. Using the research information provided, write a blog post ensuring it's between 5000 and 8000 words long.",
                                  f"Research Info: {research_report}\nPrompt: {initial_directive}\nKeyword: {target_keyword}")
    total_tokens += tokens

    # Graphic Designer Role
    draft_with_images, tokens = safe_api_call("gpt-4",
                                              "You are a graphic designer. Suggest where and what images to add in the blog post by placing descriptions in square brackets at the appropriate places.",
                                              draft)
    total_tokens += tokens

    # SEO Specialist Role
    seo_feedback, tokens = safe_api_call("gpt-4",
                                         f"You are an SEO professional. Review the following article based on the keyword '{target_keyword}'. Give a bulleted list of feedback and advice for the content writer. ",
                                         draft_with_images, total_tokens)
    total_tokens += tokens

    # Editor Role
    editor_feedback, tokens = safe_api_call("gpt-4",
                                            f"You are an editor with 10+ years of experience. Review the following article. Checks the content for clarity, coherence, consistency, grammar, and punctuation. Give a bulleted list of feedback and advice for the content writer. ",
                                            draft_with_images, total_tokens)
    total_tokens += tokens

    # Senior Editor Role
    senior_editor_feedback, tokens = safe_api_call("gpt-4",
                                                   "You are a senior editor with 15+ years of experience. Review the following article. Check the content for clarity, coherence, consistency, grammar, and punctuation. Give a bulleted list of feedback and advice for the content writer.",
                                                   draft_with_images, total_tokens)
    total_tokens += tokens

    # Feedback Integration
    revised_draft, tokens = safe_api_call("gpt-4",
                                          "You are a professional content writer. Integrate the feedback from the editor, senior editor, SEO specialist, and graphic designer to produce a refined draft.",
                                          f"Original Draft: {draft_with_images}\nEditor Feedback: {editor_feedback}\nSenior Editor Feedback: {senior_editor_feedback}\nSEO Feedback: {seo_feedback}")
    total_tokens += tokens

    # Audience Feedback Simulation
    audience_feedback, tokens = safe_api_call("gpt-4",
                                              "You represent the target audience for this blog post. Provide feedback on its relevance, interest, and any areas of improvement.",
                                              revised_draft)
    total_tokens += tokens

    # Rewrite based on Audience Feedback
    audience_revised_draft, tokens = safe_api_call("gpt-4",
                                                   "You are a professional content writer. Integrate the feedback from the audience to further refine the draft.",
                                                   f"Original Draft: {revised_draft}\nAudience Feedback: {audience_feedback}")
    total_tokens += tokens

    # Second Senior Editor Feedback Loop
    second_senior_editor_feedback, tokens = safe_api_call("gpt-4",
                                                          "You are a senior editor with 15+ years of experience. Review the audience-revised draft. Check the content for clarity, coherence, consistency, grammar, and punctuation. Give a bulleted list of feedback and advice for the content writer.",
                                                          audience_revised_draft, total_tokens)
    total_tokens += tokens

    # Rewrite based on Second Senior Editor Feedback
    final_draft, tokens = safe_api_call("gpt-4",
                                        "You are a professional content writer. Integrate the feedback from the second senior editor review to finalize the draft.",
                                        f"Original Draft: {audience_revised_draft}\nSecond Senior Editor Feedback: {second_senior_editor_feedback}")
    total_tokens += tokens

    # Creative Writer Role for Title Suggestion
    suggested_title, tokens = safe_api_call("gpt-4",
                                            "You are a creative writer. Suggest a captivating title for the article. The audience are people interested in the art market.",
                                            initial_directive, total_tokens)
    total_tokens += tokens

    # You can continue with the rest of your code here, such as saving the final draft to a PDF or any other post-processing steps.

    # You can continue with the rest of your code here, such as saving the final draft to a PDF or any other post-processing steps.
    cleaned_draft = re.sub(r'<.*?>', '', final_draft)
    cleaned_draft = remove_non_latin1_characters(cleaned_draft)

    filename = generate_pdf(target_keyword, cleaned_draft)
    print(f"Final draft saved as '{filename}'")

    total_cost = calculate_cost(total_tokens)
    print(f"Total cost for {total_tokens} tokens: ${total_cost:.2f}")

if __name__ == "__main__":
    main()

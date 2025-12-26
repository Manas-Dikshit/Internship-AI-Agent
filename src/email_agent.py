import logging
from openai import OpenAI
from typing import Dict, Any

logger = logging.getLogger(__name__)

class EmailGenerator:
    def __init__(self, api_key: str, config: Dict[str, Any]):
        self.client = OpenAI(api_key=api_key)
        self.config = config
        self.model = config.get("model", "gpt-4o-mini")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 600)
        self.system_prompt = config.get("system_prompt", "You are a helpful assistant writing professional job application emails.")

    def generate_email(self, job_details: Dict[str, str], resume_text: str, template: str) -> str:
        """Generates a personalized cold email using OpenAI."""
        
        company = job_details.get("company", "the company")
        role = job_details.get("title", "the role")
        
        # Truncate resume if needed or configured
        if self.config.get("include_resume_summary", True):
            resume_context = f"My Resume Content:\n{resume_text[:2000]}..." # Limit context
        else:
            resume_context = "Resume attached."

        prompt = f"""
        Task: Write a highly personalized, professional cold email applying for an internship.
        
        Target:
        Role: {role}
        Company: {company}
        Job Description Snippet: "{job_details.get("description", "N/A")[:600]}..."
        
        My Profile (Resume Excerpt):
        "{resume_text[:2500]}"
        
        Instructions:
        1. **Tone**: Professional, confident, enthusiastic, yet concise. Avoid generic fluff.
        2. **Structure**: Follow the template below strictly for layout, but fill the body with specific details connecting my skills to their requirements.
        3. **Customization**: Mention specific technologies from the job description that I also have in my resume.
        4. **Subject Line**: If the template includes a subject line, optimize it to be catchy (e.g., "Java Developer Intern Application - [My Name]").
        5. **No Placeholders**: Do NOT leave any brackets like [Insert Skill] or [Date]. Fill them based on the data provided. If unknown, use a generic professional alternative.
        
        Template:
        {template}
        """

        try:
            logger.info(f"Generating email for {role} at {company}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            email_content = response.choices[0].message.content.strip()
            return email_content

        except Exception as e:
            logger.error(f"Error generating email: {e}")
            return ""

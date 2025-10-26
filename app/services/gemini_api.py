import google.generativeai as genai
import os
import json
import re
from dotenv import load_dotenv  # Add this import

# Load environment variables from .env file
load_dotenv()

class GeminiAPI:
    def __init__(self, api_key=None):
        # Corrected: Use environment variable name, not the actual key
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        
        if not self.api_key:
            print("⚠️ GEMINI_API_KEY environment variable not found")
            print("   Please create a .env file with GEMINI_API_KEY=your_actual_key")
            self.model = None
            return
            
        try:
            genai.configure(api_key=self.api_key)
            # Use gemini-1.5-flash (free, fast, and better for this use case)
            self.model = genai.GenerativeModel('gemini-2.5-flash')
            print("✅ Gemini Flash API initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize Gemini API: {str(e)}")
            self.model = None
    
    def is_available(self):
        return self.model is not None
    
    def generate_questions(self, context, num_questions=10, difficulty="medium"):
        """
        Generate quiz questions using Gemini Flash API
        """
        if not self.is_available():
            print("❌ Gemini API is not available")
            return None
        
        # Define difficulty-specific instructions
        difficulty_instructions = {
            "easy": """
            EASY DIFFICULTY:
            - Test basic recall and understanding
            - Use simple, straightforward language
            - Correct answers should be obvious from direct context
            - Focus on key terms and main ideas
            """,
            "medium": """
            MEDIUM DIFFICULTY:
            - Test comprehension and application
            - Require some analysis and interpretation
            - Include questions that connect different concepts
            - Distractors should be plausible but incorrect
            """,
            "hard": """
            HARD DIFFICULTY:
            - Test analysis, synthesis, and evaluation
            - Require critical thinking and deeper understanding
            - Include complex scenarios and subtle distinctions
            - Distractors should be very close to correct answer
            """
        }
        
        prompt = f"""
        CONTEXT: {context[:6000]}
        
        TASK: Generate EXACTLY {num_questions} quiz questions based ONLY on the context above.
        DIFFICULTY LEVEL: {difficulty.upper()}
        {difficulty_instructions.get(difficulty, difficulty_instructions['medium'])}
        
        QUESTION TYPE VARIETY:
        Include a mix of these question types:
        - MULTIPLE CHOICE (MCQ): Standard multiple choice with 4 options
        - TRUE/FALSE: Clear true/false statements  
        - FILL IN THE BLANKS: Sentences with blanks and 4 word options
        - STATEMENT TYPE: Two statements with relationship analysis
        
        IMPORTANT: Generate EXACTLY {num_questions} questions total.
        
        FOR EACH QUESTION, PROVIDE:
        - question: Clear question text (for Statement type, include both statements)
        - type: "MCQ", "TrueFalse", "FillInBlank", or "Statement"
        - options: Array of 4 options (consistent for all types)
        - answer: Correct answer (letter A, B, C, D or "True"/"False")
        - explanation: Brief explanation referencing the context
        - difficulty: "{difficulty}"
        
        OUTPUT FORMAT (STRICT JSON):
        {{
            "questions": [
                {{
                    "question": "What is the main topic discussed?",
                    "type": "MCQ",
                    "options": ["Topic A", "Topic B", "Topic C", "Topic D"],
                    "answer": "A",
                    "explanation": "The context clearly states that Topic A is the main focus...",
                    "difficulty": "{difficulty}"
                }},
                {{
                    "question": "The context states that AI will replace all jobs.",
                    "type": "TrueFalse", 
                    "options": ["True", "False"],
                    "answer": "False",
                    "explanation": "The context mentions AI will transform jobs, not replace all of them.",
                    "difficulty": "{difficulty}"
                }},
                {{
                    "question": "Machine learning is a subset of _____ intelligence.",
                    "type": "FillInBlank",
                    "options": ["artificial", "human", "natural", "synthetic"],
                    "answer": "A",
                    "explanation": "The context defines machine learning as a subset of artificial intelligence.",
                    "difficulty": "{difficulty}"
                }},
                {{
                    "question": "Statement I: Machine learning requires large datasets. Statement II: All AI systems use neural networks.",
                    "type": "Statement",
                    "options": [
                        "Both Statement I and Statement II are true",
                        "Statement I is true but Statement II is false", 
                        "Statement I is false but Statement II is true",
                        "Both Statement I and Statement II are false"
                    ],
                    "answer": "B",
                    "explanation": "Statement I is true as context mentions ML needs data. Statement II is false as not all AI uses neural networks.",
                    "difficulty": "{difficulty}"
                }}
            ]
        }}
        
        CRITICAL REQUIREMENTS:
        1. Generate EXACTLY {num_questions} questions - no more, no less
        2. ALL questions must be answerable from the context ONLY
        3. For ALL question types, always provide exactly 4 options
        4. Return ONLY valid JSON, no additional text
        5. Ensure questions are diverse and cover different aspects of the context
        """
        
        try:
            print(f"🧠 Generating EXACTLY {num_questions} {difficulty} questions using Gemini Flash...")
            
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    top_p=0.8,
                    top_k=40,
                    max_output_tokens=8192,  # Increased for more questions
                )
            )
            
            text = response.text.strip()
            print(f"📝 Raw response received: {len(text)} characters")
            
            # Clean the response
            text = re.sub(r'```json\s*|\s*```', '', text)
            text = text.strip()
            
            data = json.loads(text)
            questions = data.get("questions", [])
            
            print(f"📊 Gemini returned {len(questions)} questions")
            
            # Validate and clean questions - be less strict
            validated_questions = []
            for i, q in enumerate(questions):
                cleaned_q = self._clean_question(q)
                if cleaned_q:
                    validated_questions.append(cleaned_q)
                else:
                    print(f"⚠️ Question {i+1} filtered out during cleaning")
            
            print(f"✅ After validation: {len(validated_questions)} questions")
            
            # If we got fewer questions than requested, log warning but return what we have
            if len(validated_questions) < num_questions:
                print(f"⚠️ WARNING: Requested {num_questions} but got {len(validated_questions)} valid questions")
            
            return validated_questions
            
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON response: {str(e)}")
            print(f"Raw response: {text[:500]}...")
            return None
        except Exception as e:
            print(f"❌ Gemini API Error: {str(e)}")
            return None
    
    def _clean_question(self, question):
        """Clean and validate individual question - more lenient"""
        try:
            # Required fields
            if not all(key in question for key in ['question', 'type', 'options', 'answer']):
                print(f"⚠️ Missing required fields in question")
                return None
            
            # Ensure question text is not empty
            if not question['question'] or not question['question'].strip():
                print(f"⚠️ Empty question text")
                return None
            
            # Ensure options is a list with at least 2 items
            if not isinstance(question['options'], list) or len(question['options']) < 2:
                print(f"⚠️ Invalid options format")
                return None
            
            # If we have fewer than 4 options, pad with generic ones
            if len(question['options']) < 4:
                print(f"⚠️ Only {len(question['options'])} options, padding to 4")
                while len(question['options']) < 4:
                    question['options'].append(f"Option {len(question['options']) + 1}")
            
            # Clean answer format
            original_answer = question['answer']
            if question['type'] in ['MCQ', 'FillInBlank', 'Statement']:
                if isinstance(question['answer'], int) and 0 <= question['answer'] < 4:
                    question['answer'] = ['A', 'B', 'C', 'D'][question['answer']]
                elif isinstance(question['answer'], str):
                    # Extract first letter and convert to uppercase
                    match = re.search(r'[A-D]', question['answer'].upper())
                    if match:
                        question['answer'] = match.group()
                    else:
                        # Default to A if cannot parse
                        question['answer'] = 'A'
                        print(f"⚠️ Could not parse answer '{original_answer}', defaulting to A")
            
            elif question['type'] == 'TrueFalse':
                if isinstance(question['answer'], bool):
                    question['answer'] = 'True' if question['answer'] else 'False'
                elif isinstance(question['answer'], str):
                    if question['answer'].lower() in ['true', 't', 'yes', 'y', 'a']:
                        question['answer'] = 'True'
                    elif question['answer'].lower() in ['false', 'f', 'no', 'n', 'b']:
                        question['answer'] = 'False'
                    else:
                        # Default to False if cannot parse
                        question['answer'] = 'False'
                        print(f"⚠️ Could not parse TrueFalse answer '{original_answer}', defaulting to False")
            
            # Ensure explanation exists
            if 'explanation' not in question or not question['explanation']:
                question['explanation'] = "Based on the provided context."
            
            # Ensure difficulty is set
            if 'difficulty' not in question:
                question['difficulty'] = 'medium'
            
            return question
            
        except Exception as e:
            print(f"⚠️ Question cleaning failed: {e}")
            return None
    
    def _validate_statement_question(self, question):
        """Validate Statement type question format"""
        question_text = question.get('question', '')
        
        # Check if question contains two statements
        if 'Statement I:' not in question_text or 'Statement II:' not in question_text:
            return False
        
        # Check if options follow the standard Statement format
        expected_options = [
            "Both Statement I and Statement II are true",
            "Statement I is true but Statement II is false", 
            "Statement I is false but Statement II is true",
            "Both Statement I and Statement II are false"
        ]
        
        # Allow some flexibility in option wording
        user_options = [opt.lower() for opt in question['options']]
        expected_lower = [opt.lower() for opt in expected_options]
        
        # Check if at least 3 out of 4 expected options are present
        matches = sum(1 for expected in expected_lower if any(expected in user_opt for user_opt in user_options))
        return matches >= 3

# Global instance
gemini_api = GeminiAPI()
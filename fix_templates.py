import os
import re

def fix_template_urls():
    template_dir = 'app/templates'
    
    # URL mapping from old to new
    url_mappings = {
        'routes\.index': 'auth.index',
        'routes\.login': 'auth.login', 
        'routes\.register': 'auth.register',
        'routes\.logout': 'auth.logout',
        'routes\.dashboard': 'quiz.dashboard',
        'routes\.upload_file': 'quiz.upload_file',
        'routes\.generate_questions': 'quiz.generate_questions',
        'routes\.take_quiz': 'quiz.take_quiz',
        'routes\.save_attempt': 'quiz.save_attempt',
        'routes\.history': 'progress.history',
        'routes\.progress': 'progress.progress',
        'routes\.view_attempt': 'progress.view_attempt',
        'routes\.retake_quiz': 'progress.retake_quiz',
        'routes\.settings': 'settings.settings',
        'routes\.update_profile': 'settings.update_profile',
        'routes\.change_password': 'settings.change_password',
        'routes\.update_preferences': 'settings.update_preferences',
        'routes\.delete_account': 'settings.delete_account'
    }
    
    for filename in os.listdir(template_dir):
        if filename.endswith('.html'):
            filepath = os.path.join(template_dir, filename)
            print(f"Updating {filename}...")
            
            with open(filepath, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Apply all replacements
            for old_pattern, new_value in url_mappings.items():
                content = re.sub(old_pattern, new_value, content)
            
            # Write updated content back
            with open(filepath, 'w', encoding='utf-8') as file:
                file.write(content)
    
    print("✅ All templates updated successfully!")

if __name__ == "__main__":
    fix_template_urls()
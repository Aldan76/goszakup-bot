import sys, os
sys.path.insert(0, r'C:\Users\fazyl\Documents\Project1\goszakup-bot')
from dotenv import load_dotenv
load_dotenv(r'C:\Users\fazyl\Documents\Project1\goszakup-bot\.env', override=True)
from rag import answer_question
print('Тест: задаём вопрос...')
print('=' * 60)
answer = answer_question('Какие основания для закупки из одного источника?', [])
print(answer)
print('=' * 60)
print('ТЕСТ ПРОШЁЛ УСПЕШНО')

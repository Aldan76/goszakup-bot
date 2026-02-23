"""
Conversation Context Manager
Upravlyaet kontekstom dialoga - tema, platforma, istorija
"""
from typing import Optional
from datetime import datetime, timedelta

class ConversationContext:
    """Manages conversation context across multiple turns"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.platform: Optional[str] = None  # goszakup, omarket
        self.topic: Optional[str] = None      # pitanie, dvc, ktp, etc
        self.last_updated = datetime.now()
        self.conversation_history = []
        self.confidence_score = 0.0  # 0.0-1.0
        
    def update_context(self, question: str, detected_platform: Optional[str], 
                      detected_topic: Optional[str], confidence: float = 0.7):
        """Update context based on new question"""
        
        # Only update if confidence is high enough OR explicitly stated
        if detected_platform and confidence > 0.6:
            self.platform = detected_platform
            self.confidence_score = confidence
            self.last_updated = datetime.now()
        
        if detected_topic and confidence > 0.6:
            self.topic = detected_topic
            self.last_updated = datetime.now()
        
        self.conversation_history.append({
            'question': question,
            'platform': detected_platform,
            'topic': detected_topic,
            'timestamp': datetime.now(),
            'confidence': confidence
        })
    
    def get_context_hint(self) -> str:
        """Get hint about current context for RAG"""
        if self.platform or self.topic:
            hints = []
            if self.platform:
                hints.append(f"Platform context: {self.platform}")
            if self.topic:
                hints.append(f"Topic context: {self.topic}")
            return " | ".join(hints)
        return ""
    
    def get_assumed_platform(self) -> Optional[str]:
        """Return assumed platform from context"""
        # Only return if context is fresh (less than 5 minutes old)
        if self.platform:
            age = datetime.now() - self.last_updated
            if age < timedelta(minutes=5):
                return self.platform
        return None
    
    def reset(self):
        """Reset context (e.g., when user starts new topic)"""
        self.platform = None
        self.topic = None
        self.confidence_score = 0.0
        self.conversation_history = []
    
    def __repr__(self):
        return (f"ConversationContext(platform={self.platform}, topic={self.topic}, "
                f"confidence={self.confidence_score:.1f})")


def infer_topic_from_question(question: str) -> Optional[str]:
    """Infer topic from question keywords"""
    
    topic_keywords = {
        'pitanie': ['питани', 'завтрак', 'обед', 'ужин', 'школ', 'детск', 'столов'],
        'dvc': ['внутристран', 'казахстанског', 'дvc'],
        'ktp': ['товаропроизводител', 'кtp', 'местн'],
        'omarket': ['магазин', 'каталог', 'товар', 'прайс', 'омаркет'],
        'goszakup': ['закупк', 'портал', 'госзакуп', 'аукцион', 'объявлени'],
    }
    
    q_lower = question.lower()
    
    for topic, keywords in topic_keywords.items():
        for keyword in keywords:
            if keyword in q_lower:
                return topic
    
    return None


def enhance_question_with_context(question: str, context: ConversationContext) -> str:
    """Add context to question for better RAG search"""
    
    context_hint = context.get_context_hint()
    if context_hint:
        return f"{question}\n[Context: {context_hint}]"
    return question


# Example: How to use in Telegram bot

EXAMPLE_BOT_USAGE = '''
# Integration in bot.py:

from telegram.ext import ContextTypes
from conversation_context import ConversationContext, infer_topic_from_question

# Store contexts in application.context_types.user_data
# Key: user_id, Value: ConversationContext

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    question = update.message.text.strip()
    
    # === NEW: Get or create conversation context ===
    if 'conversation_context' not in context.user_data:
        context.user_data['conversation_context'] = ConversationContext(user_id)
    
    conv_context = context.user_data['conversation_context']
    
    # === Step 1: Detect platform (with context memory) ===
    detected_platform = detect_platform(question)
    
    # If not explicitly stated, use context memory
    if not detected_platform and conv_context.get_assumed_platform():
        detected_platform = conv_context.get_assumed_platform()
        print(f"[Context Memory] Using platform from context: {detected_platform}")
    
    # === Step 2: Detect topic ===
    detected_topic = infer_topic_from_question(question)
    
    # === Step 3: Update context ===
    confidence = 0.9 if detected_platform else 0.6
    conv_context.update_context(question, detected_platform, detected_topic, confidence)
    
    # === Step 4: Search with context ===
    enhanced_question = enhance_question_with_context(question, conv_context)
    answer, chunks, _ = answer_question(enhanced_question, [])
    
    await update.message.reply_text(answer)


# Example conversation flow:

User: "Какие процедуры для закупок питания в школах?"
  → detect_platform() = None
  → infer_topic() = "pitanie"
  → Context updated: platform=None, topic=pitanie
  → RAG search includes: topic context = pitanie

User: "Какова минимальная стоимость?"
  → detect_platform() = None (амбигуозно!)
  → infer_topic() = None (нет ключевых слов)
  → Context memory: topic=pitanie from previous question
  → RAG search automatically filters for pitanie documents!
  → Result: Правильный ответ о стоимости питания ✓

User: "А что если я работаю на omarket?"
  → detect_platform() = "omarket"
  → Context reset OR updated: platform=omarket
  → Context awareness: User switched topics
  → RAG search now uses omarket context
'''

if __name__ == '__main__':
    # Test
    ctx = ConversationContext(user_id=12345)
    
    print("Test 1: First question about питание")
    ctx.update_context(
        "Как проводятся закупки питания в школах?",
        detected_platform=None,
        detected_topic="pitanie",
        confidence=0.8
    )
    print(f"Context: {ctx}")
    print(f"Assumed platform: {ctx.get_assumed_platform()}")
    print()
    
    print("Test 2: Follow-up question")
    ctx.update_context(
        "Какова минимальная стоимость?",
        detected_platform=None,
        detected_topic=None,
        confidence=0.0
    )
    print(f"Context: {ctx}")
    print(f"Assumed platform: {ctx.get_assumed_platform()}")
    print(f"Topic remembered: {ctx.topic}")
    print()
    
    print("Test 3: Switch to omarket")
    ctx.update_context(
        "А как это работает на omarket?",
        detected_platform="omarket",
        detected_topic=None,
        confidence=0.95
    )
    print(f"Context: {ctx}")

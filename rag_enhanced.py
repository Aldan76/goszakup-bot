"""
Enhanced RAG with clarification questions for ambiguous searches
Uluchshennaya versiya s podderzhkoj utochnyayushchih voprosov
"""

def search_with_platform_tracking(question: str, top_n: int = 4, 
                                  platform: str = None) -> list[dict]:
    """
    Search and track which platform the results came from.
    Returns chunks with 'source_platform' field populated.
    """
    from rag import search_supabase
    
    if platform:
        chunks = search_supabase(question, top_n=top_n, platform=platform)
        # Already have source_platform from database
        return chunks
    else:
        # Search all and return with platform info
        chunks = search_supabase(question, top_n=top_n)
        return chunks


def get_platforms_found(chunks: list[dict]) -> set:
    """Extract unique platforms from search results"""
    platforms = set()
    for chunk in chunks:
        platform = chunk.get('source_platform')
        if platform and platform not in ('all',):  # Exclude 'all' platform
            platforms.add(platform)
    return platforms


def needs_clarification(question: str, platforms_found: set) -> bool:
    """
    Determine if user clarification is needed.
    
    Returns True if:
    - No explicit platform mentioned in question AND
    - Results found from multiple platforms AND
    - Those platforms are omarket or goszakup (user-facing platforms)
    """
    from rag import detect_platform
    
    # Check if platform was explicitly mentioned
    platform = detect_platform(question)
    if platform:
        return False  # User already specified
    
    # Check if we have conflicting platform results
    user_platforms = {'omarket', 'goszakup'} & platforms_found
    return len(user_platforms) > 1


def get_clarification_message(platforms_found: set) -> str:
    """Generate clarification question message"""
    
    platform_names = {
        'omarket': 'Omarket.kz (электронный магазин закупок)',
        'goszakup': 'goszakup.gov.kz (портал государственных закупок)',
    }
    
    user_platforms = ['omarket', 'goszakup']
    available = [p for p in user_platforms if p in platforms_found]
    
    if not available:
        return None
    
    if len(available) == 1:
        return None
    
    # Multiple platforms
    msg = (
        "Ваш вопрос может относиться к нескольким платформам.\n\n"
        "Пожалуйста, уточните какой сайт вас интересует:\n\n"
    )
    
    for i, platform in enumerate(available, 1):
        msg += f"{i}. {platform_names.get(platform, platform)}\n"
    
    msg += (
        "\nОтветьте цифрой (1, 2) или названием платформы "
        "(например: 'omarket' или 'goszakup')"
    )
    
    return msg


def parse_platform_response(response: str) -> str:
    """Parse user response to clarification question"""
    response_lower = response.lower().strip()
    
    # Map various responses to platform names
    platform_map = {
        '1': 'omarket',
        '2': 'goszakup',
        'omarket': 'omarket',
        'омаркет': 'omarket',
        'магазин': 'omarket',
        'goszakup': 'goszakup',
        'госзакуп': 'goszakup',
        'портал': 'goszakup',
    }
    
    for key, platform in platform_map.items():
        if key in response_lower:
            return platform
    
    return None


# Example usage in bot
EXAMPLE_BOT_USAGE = """
# How to use in bot.py:

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = update.message.text.strip()
    
    # Check if we need to ask for clarification
    temp_chunks = search_supabase(question, top_n=3)  # Quick search
    platforms_found = get_platforms_found(temp_chunks)
    
    if needs_clarification(question, platforms_found):
        clarification_msg = get_clarification_message(platforms_found)
        await update.message.reply_text(clarification_msg)
        
        # Store question in user_data for next message
        context.user_data['pending_question'] = question
        context.user_data['waiting_for_clarification'] = True
        return
    
    # If user is responding to clarification
    if context.user_data.get('waiting_for_clarification'):
        platform = parse_platform_response(question)
        if platform:
            original_question = context.user_data['pending_question']
            context.user_data['waiting_for_clarification'] = False
            # Search with specific platform
            answer, chunks_count, _ = answer_question(original_question, [])
            await update.message.reply_text(answer)
        else:
            await update.message.reply_text(
                "Не смог понять платформу. Пожалуйста, ответьте 'omarket' или 'goszakup'"
            )
        return
    
    # Regular question handling
    answer, chunks_count, _ = answer_question(question, [])
    await update.message.reply_text(answer)
"""

if __name__ == '__main__':
    print("RAG Enhanced Module")
    print("="*70)
    print(EXAMPLE_BOT_USAGE)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import yaml
import html
import random
import re
from typing import Dict, Any, List, Tuple

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from aiogram.types import PollAnswer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PollBot:
    def __init__(
        self,
        secrets_config_path: str = "secrets_config.yaml",
        poll_config_path: str = "poll_config.yaml"
    ):
        """Initialize the poll bot with configuration."""
        self.secrets_config = self.load_config(secrets_config_path)
        self.poll_config = self.load_config(poll_config_path)
        self.bot = Bot(token=self.secrets_config['telegram_bot']['token'])
        self.storage = MemoryStorage()
        self.dp = Dispatcher(self.bot, storage=self.storage)
        self.polls = self.poll_config.get('polls', [])
        
        # Create polls dictionary for quick lookup by number
        self.polls_by_number = {
            poll['number']: poll for poll in self.polls if 'number' in poll
        }
        
        # Register handlers
        self.register_handlers()
    
    def load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            logger.error(f"Config file {config_path} not found!")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML config: {e}")
            raise
    
    def register_handlers(self):
        """Register all bot handlers."""
        
        @self.dp.message_handler(commands=['start'])
        async def start_command(message: types.Message):
            """Handle /start command."""
            welcome_text = (
                "🤖 Group Poll Bot\n\n"
                "I can create polls in this group using predefined questions.\n\n"
                "Available commands:\n"
                "/make_poll [poll_number] - Create a poll by number\n"
                "/choice [names] - Randomly choose from a list of names\n"
                "/question - Send a random question from file\n"
                "/list_polls - List all available polls\n"
                "/help - Show help information\n\n"
                "Example:\n"
                "/make_poll 0 - Creates a poll by number\n"
                "/make_poll 1 - Creates another poll by number"
            )
            await message.answer(welcome_text)
        
        @self.dp.message_handler(commands=['help'])
        async def help_command(message: types.Message):
            """Handle /help command."""
            help_text = (
                "📋 How to use Group Poll Bot:\n\n"
                "1. Use /list_polls to see all available polls\n"
                "2. Use /make_poll [poll_number] to create a specific poll\n"
                "3. Use /choice [names] to randomly choose from a list\n"
                "4. Use /question to send a random question\n\n"
                "Examples:\n"
                "• /make_poll 0 - First poll\n"
                "• /make_poll 1 - Second poll\n"
                "• /choice John, Bob, Juan, Roman - Randomly choose a name\n\n"
                "Poll Types:\n"
                "• Regular polls - Multiple choice questions\n"
                "• Quiz polls - Questions with correct answers\n\n"
                "Note: Poll numbers are defined in the poll configuration."
            )
            await message.answer(help_text)
        
        @self.dp.message_handler(commands=['list_polls'])
        async def list_polls_command(message: types.Message):
            """List all available polls with their numbers."""
            if not self.polls:
                await message.answer("❌ No polls available in configuration.")
                return
            
            poll_list = "📊 Available Polls:\n\n"
            for poll in self.polls:
                poll_type = "🧩 Quiz" if poll.get('type') == 'quiz' else "📝 Regular"
                poll_list += f"Number: {poll['number']}\n"
                poll_list += f"ID: {poll['id']}\n"
                poll_list += f"Question: {poll['question']}\n"
                poll_list += f"Type: {poll_type}\n"
                poll_list += f"Options: {len(poll.get('options', []))}\n\n"
            
            poll_list += "Usage: /make_poll [poll_number]\n"
            poll_list += "Example: /make_poll 0"
            
            await message.answer(poll_list)
        
        @self.dp.message_handler(commands=['make_poll'])
        async def make_poll_command(message: types.Message):
            """Create a poll by number."""
            # Check if command has arguments
            if not message.get_args():
                await message.answer(
                    "❌ Usage: /make_poll [poll_number]\n\n"
                    "Example: /make_poll 0\n\n"
                    "Use /list_polls to see available poll numbers."
                )
                return
            
            poll_number_raw = message.get_args().strip()
            if not poll_number_raw.isdigit():
                await message.answer(
                    "❌ Poll number must be a non-negative integer.\n\n"
                    "Example: /make_poll 0"
                )
                return
            
            poll_number = int(poll_number_raw)
            
            # Check if poll exists
            if poll_number not in self.polls_by_number:
                available_numbers = ", ".join(
                    [str(poll['number']) for poll in self.polls if 'number' in poll]
                )
                await message.answer(
                    f"❌ Poll number not found: {poll_number}\n\n"
                    f"Available poll numbers: {available_numbers}\n\n"
                    "Use /list_polls for more details."
                )
                return
            
            # Get poll data
            poll_data = self.polls_by_number[poll_number]
            
            try:
                # Create the poll
                await self.create_poll_in_chat(
                    message.chat.id,
                    poll_data
                )
                
                # Send confirmation message
                poll_type = "🧩 Quiz" if poll_data.get('type') == 'quiz' else "📝 Regular"
                is_anonymous = "Anonymous" if poll_data.get('is_anonymous', True) else "Not Anonymous"
                multiple_answers = "Multiple answers allowed" if poll_data.get('allows_multiple_answers', False) else "Single answer only"
                
                logger.info(f"Poll '{poll_number}' created in chat {message.chat.id} by user {message.from_user.id}")
                
            except Exception as e:
                logger.error(f"Error creating poll {poll_number}: {e}")
                await message.answer(
                    f"❌ Error creating poll: {str(e)}\n\n"
                    "Please try again or contact an administrator."
                )
        
        
        @self.dp.message_handler(commands=['choice'])
        async def choice_command(message: types.Message):
            """Randomly choose from a list of names."""
            # Check if command has arguments
            if not message.get_args():
                await message.answer(
                    "❌ Usage: /choice [names separated by commas]\n\n"
                    "Example: /choice John, Bob, Juan, Roman\n\n"
                    "The bot will randomly select one name from the list."
                )
                return
            
            names_input = message.get_args().strip()
            
            try:
                # Split names by comma and clean them
                names = [name.strip() for name in names_input.split(',') if name.strip()]
                
                if len(names) < 2:
                    await message.answer(
                        "❌ Please provide at least 2 names separated by commas.\n\n"
                        "Example: /choice John, Bob, Juan, Roman"
                    )
                    return
                
                # Randomly select a name
                chosen_name = random.choice(names)
                
                # Create a nice response
                names_list = ", ".join(names)
                response = (
                    f"🎲 **Random Choice**\n\n"
                    f"From: {names_list}\n\n"
                    f"🎯 **Chosen:** {chosen_name}"
                )
                
                await message.answer(response, parse_mode='Markdown')
                
                logger.info(f"Random choice made by user {message.from_user.id}: {chosen_name} from {names}")
                
            except Exception as e:
                logger.error(f"Error in choice command: {e}")
                await message.answer(
                    "❌ Error processing the choice command.\n\n"
                    "Please make sure to separate names with commas.\n"
                    "Example: /choice John, Bob, Juan, Roman"
                )
        
        @self.dp.message_handler(commands=['question'])
        async def question_command(message: types.Message):
            """Send a random question from the local pack file."""
            try:
                question_text, spoiler_text = self.get_random_question_block("random_pack.txt")
            except FileNotFoundError:
                await message.answer("❌ File random_pack.txt not found.")
                return
            except ValueError as e:
                await message.answer(f"❌ {str(e)}")
                return
            except Exception as e:
                logger.error(f"Error loading question: {e}")
                await message.answer("❌ Error loading question.")
                return
            
            if spoiler_text:
                question_chunks = self.split_message_chunks(question_text)
                spoiler_chunks = self.split_message_chunks(spoiler_text)
                
                for chunk in question_chunks:
                    await message.answer(self.escape_html(chunk), parse_mode='HTML')
                
                for chunk in spoiler_chunks:
                    payload = f"<span class=\"tg-spoiler\">{self.escape_html(chunk)}</span>"
                    await message.answer(payload, parse_mode='HTML')
            else:
                for chunk in self.split_message_chunks(question_text):
                    await message.answer(self.escape_html(chunk), parse_mode='HTML')
        
        @self.dp.poll_answer_handler()
        async def handle_poll_answer(poll_answer: PollAnswer):
            """Handle poll answers (optional - for analytics)."""
            logger.info(f"Poll answer received: User {poll_answer.user.id} answered poll {poll_answer.poll_id}")
    
    def escape_markdown(self, text: str) -> str:
        """Escape special characters that might cause Markdown parsing issues."""
        # Escape common Markdown special characters
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text

    def escape_markdown_v2(self, text: str) -> str:
        """Escape text for Telegram MarkdownV2."""
        special_chars = r'_*[]()~`>#+-=|{}.!\\'
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    def escape_html(self, text: str) -> str:
        """Escape text for Telegram HTML parse mode."""
        return html.escape(text)
    
    def split_message_chunks(self, text: str, max_len: int = 4000) -> List[str]:
        """Split text into chunks that fit Telegram limits."""
        if len(text) <= max_len:
            return [text]
        
        chunks = []
        current = []
        current_len = 0
        for line in text.splitlines(keepends=True):
            if len(line) > max_len:
                if current:
                    chunks.append("".join(current).strip())
                    current = []
                    current_len = 0
                for i in range(0, len(line), max_len):
                    chunks.append(line[i:i + max_len].strip())
                continue
            
            if current_len + len(line) > max_len:
                chunks.append("".join(current).strip())
                current = [line]
                current_len = len(line)
            else:
                current.append(line)
                current_len += len(line)
        
        if current:
            chunks.append("".join(current).strip())
        
        return [chunk for chunk in chunks if chunk]
    
    def get_random_question_block(self, file_path: str) -> Tuple[str, str]:
        """Load a random question block and split it into visible/spoiler parts."""
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        blocks: List[str] = []
        current: List[str] = []
        for line in content.splitlines():
            current.append(line)
            if line.lower().startswith("автор:") or line.lower().startswith("авторка:"):
                block = "\n".join(current).strip()
                if block:
                    blocks.append(block)
                current = []
        
        trailing = "\n".join(current).strip()
        if trailing:
            blocks.append(trailing)
        
        if not blocks:
            raise ValueError("No question blocks found in random_pack.txt.")
        
        block = random.choice(blocks)
        if len(block) > 10000:
            raise ValueError("Selected block is too long (over 10000 characters).")
        block_lines = block.splitlines()
        
        # Trim any preamble before the first "Вопрос" line
        question_start = None
        for idx, line in enumerate(block_lines):
            if line.strip().startswith("Вопрос"):
                question_start = idx
                break
        if question_start is not None:
            block_lines = block_lines[question_start:]
        
        spoiler_index = None
        for idx, line in enumerate(block_lines):
            if line.strip().startswith("Ответ:"):
                spoiler_index = idx
                break
        
        if spoiler_index is None:
            return "\n".join(block_lines).strip(), ""
        
        question_text = "\n".join(block_lines[:spoiler_index]).strip()
        spoiler_text = "\n".join(block_lines[spoiler_index:]).strip()
        return question_text, spoiler_text
    
    
    async def create_poll_in_chat(self, chat_id: int, poll_data: Dict[str, Any]) -> types.Message:
        """Create a poll in the specified chat."""
        question = self.escape_markdown(poll_data['question'])
        options = [self.escape_markdown(option) for option in poll_data['options']]
        poll_type = poll_data.get('type', 'regular')
        
        # Get new poll options
        is_anonymous = poll_data.get('is_anonymous', True)
        allows_multiple_answers = poll_data.get('allows_multiple_answers', False)
        
        # Prepare poll parameters
        poll_params = {
            'question': question,
            'options': options,
            'is_anonymous': is_anonymous,
            'allows_multiple_answers': allows_multiple_answers,
            'type': poll_type
        }
        
        # Add quiz-specific parameters
        if poll_type == 'quiz':
            correct_option_id = poll_data.get('correct_option_id')
            if correct_option_id is not None:
                poll_params['correct_option_id'] = correct_option_id
            
            explanation = poll_data.get('explanation')
            if explanation:
                poll_params['explanation'] = explanation
        
        # Send the poll
        poll_message = await self.bot.send_poll(chat_id=chat_id, **poll_params)
        logger.info(f"Poll created in chat {chat_id}: {question} (anonymous: {is_anonymous}, multiple: {allows_multiple_answers})")
        return poll_message
    
    def run(self):
        """Start the bot."""
        logger.info("Starting Group Poll Bot...")
        executor.start_polling(self.dp, skip_updates=True)

if __name__ == '__main__':
    try:
        bot = PollBot()
        bot.run()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

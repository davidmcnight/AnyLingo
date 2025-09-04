import os
import time
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
from abc import ABC, abstractmethod
from enum import Enum

# Translation providers
from googletrans import Translator as GoogleTranslator
from deep_translator import GoogleTranslator as DeepGoogleTranslator
from deep_translator import MicrosoftTranslator, LibreTranslator, MyMemoryTranslator
import requests


class TranslationProvider(Enum):
    """Available translation providers."""
    GOOGLE_FREE = "google_free"
    DEEP_GOOGLE = "deep_google"
    MICROSOFT_AZURE = "microsoft_azure"
    LIBRE_TRANSLATE = "libre_translate"
    MYMEMORY = "mymemory"


class TranslationProviderBase(ABC):
    """Base class for translation providers."""
    
    def __init__(self, config, provider_name: str):
        self.config = config
        self.provider_name = provider_name
        self.logger = logging.getLogger(f"{__name__}.{provider_name}")
        
    @abstractmethod
    def translate(self, text: str, source_lang: str, target_lang: str) -> Tuple[bool, str, str]:
        """
        Translate text from source to target language.
        Returns: (success, translated_text, error_message)
        """
        pass
    
    @abstractmethod
    def detect_language(self, text: str) -> Tuple[bool, str, float]:
        """
        Detect language of text.
        Returns: (success, language_code, confidence)
        """
        pass
    
    @abstractmethod
    def get_supported_languages(self) -> Dict[str, str]:
        """Get dictionary of supported language codes and names."""
        pass


class GoogleFreeProvider(TranslationProviderBase):
    """Google Translate free tier provider using googletrans library."""
    
    def __init__(self, config):
        super().__init__(config, "GoogleFree")
        self.translator = GoogleTranslator()
        self._supported_langs = None
        
    def translate(self, text: str, source_lang: str, target_lang: str) -> Tuple[bool, str, str]:
        try:
            # Handle language code mapping
            src = 'auto' if source_lang == 'auto' else source_lang
            
            result = self.translator.translate(text, src=src, dest=target_lang)
            
            if result and result.text:
                self.logger.info(f"Translated {len(text)} chars from {source_lang} to {target_lang}")
                return True, result.text, ""
            else:
                return False, "", "No translation result"
                
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Translation error: {error_msg}")
            return False, "", error_msg
    
    def detect_language(self, text: str) -> Tuple[bool, str, float]:
        try:
            result = self.translator.detect(text)
            if result:
                return True, result.lang, result.confidence
            return False, "", 0.0
        except Exception as e:
            self.logger.error(f"Language detection error: {str(e)}")
            return False, "", 0.0
    
    def get_supported_languages(self) -> Dict[str, str]:
        if self._supported_langs is None:
            # Common language codes that googletrans supports
            self._supported_langs = {
                'en': 'English',
                'es': 'Spanish',
                'fr': 'French',
                'de': 'German',
                'it': 'Italian',
                'pt': 'Portuguese',
                'ru': 'Russian',
                'ja': 'Japanese',
                'ko': 'Korean',
                'zh-cn': 'Chinese (Simplified)',
                'zh-tw': 'Chinese (Traditional)',
                'ar': 'Arabic',
                'hi': 'Hindi',
                'tr': 'Turkish',
                'pl': 'Polish',
                'nl': 'Dutch',
                'sv': 'Swedish',
                'da': 'Danish',
                'no': 'Norwegian',
                'fi': 'Finnish'
            }
        return self._supported_langs


class DeepTranslatorProvider(TranslationProviderBase):
    """Deep Translator provider with multiple backend options."""
    
    def __init__(self, config, backend='google'):
        super().__init__(config, f"DeepTranslator-{backend}")
        self.backend = backend
        
        # Initialize appropriate translator
        if backend == 'google':
            self.translator_class = DeepGoogleTranslator
        elif backend == 'microsoft':
            api_key = getattr(config, 'MICROSOFT_TRANSLATOR_KEY', None)
            if not api_key:
                raise ValueError("Microsoft Translator requires API key")
            self.translator_class = MicrosoftTranslator
            self.api_key = api_key
        elif backend == 'mymemory':
            self.translator_class = MyMemoryTranslator
        else:
            raise ValueError(f"Unsupported backend: {backend}")
            
    def translate(self, text: str, source_lang: str, target_lang: str) -> Tuple[bool, str, str]:
        try:
            # Map language codes if needed
            src = 'auto' if source_lang == 'auto' else source_lang
            
            # Create translator instance
            if self.backend == 'microsoft':
                translator = self.translator_class(
                    api_key=self.api_key,
                    source=src,
                    target=target_lang
                )
            else:
                translator = self.translator_class(
                    source=src,
                    target=target_lang
                )
            
            result = translator.translate(text)
            
            if result:
                self.logger.info(f"Translated {len(text)} chars using {self.backend}")
                return True, result, ""
            else:
                return False, "", "No translation result"
                
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Translation error with {self.backend}: {error_msg}")
            return False, "", error_msg
    
    def detect_language(self, text: str) -> Tuple[bool, str, float]:
        # Most deep_translator backends don't have language detection
        # Use a simple heuristic or return unknown
        return False, "auto", 0.0
    
    def get_supported_languages(self) -> Dict[str, str]:
        try:
            if self.backend == 'google':
                return DeepGoogleTranslator.get_supported_languages(as_dict=True)
            elif self.backend == 'mymemory':
                return MyMemoryTranslator.get_supported_languages(as_dict=True)
            else:
                return {}
        except:
            # Return common languages as fallback
            return {
                'en': 'English',
                'es': 'Spanish',
                'fr': 'French',
                'de': 'German',
                'it': 'Italian',
                'pt': 'Portuguese',
                'ru': 'Russian',
                'ja': 'Japanese',
                'ko': 'Korean',
                'zh': 'Chinese',
                'ar': 'Arabic',
                'hi': 'Hindi'
            }


class TranslationService:
    """Main translation service with multi-provider support and fallback chain."""
    
    # Language code mappings for consistency
    LANGUAGE_CODE_MAP = {
        'chinese': 'zh-cn',
        'zh': 'zh-cn',
        'chinese_simplified': 'zh-cn',
        'chinese_traditional': 'zh-tw',
        'norwegian': 'no',
        'hebrew': 'he',
        'iw': 'he',  # Old code for Hebrew
    }
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize provider chain
        self.providers = []
        self._initialize_providers()
        
        # Translation cache (simple in-memory cache)
        self.cache = {}
        self.cache_max_size = getattr(config, 'TRANSLATION_CACHE_SIZE', 1000)
        
        # Rate limiting
        self.last_request_time = {}
        self.min_request_interval = getattr(config, 'TRANSLATION_RATE_LIMIT', 0.5)
        
        # Chunk settings for long texts
        self.max_text_length = getattr(config, 'MAX_TRANSLATION_LENGTH', 5000)
        self.chunk_overlap = 50  # Characters to overlap between chunks
        
        self.logger.info(f"TranslationService initialized with {len(self.providers)} providers")
    
    def _initialize_providers(self):
        """Initialize translation providers based on configuration."""
        
        # Priority order of providers
        provider_configs = [
            ('google_free', lambda: GoogleFreeProvider(self.config)),
            ('deep_google', lambda: DeepTranslatorProvider(self.config, 'google')),
            ('mymemory', lambda: DeepTranslatorProvider(self.config, 'mymemory')),
        ]
        
        # Try to initialize Microsoft if API key is available
        if getattr(self.config, 'MICROSOFT_TRANSLATOR_KEY', None):
            provider_configs.insert(1, ('microsoft', 
                lambda: DeepTranslatorProvider(self.config, 'microsoft')))
        
        for name, initializer in provider_configs:
            try:
                provider = initializer()
                self.providers.append(provider)
                self.logger.info(f"Initialized provider: {name}")
            except Exception as e:
                self.logger.warning(f"Failed to initialize {name}: {str(e)}")
        
        if not self.providers:
            raise RuntimeError("No translation providers could be initialized")
    
    def translate(self, 
                 text: str, 
                 target_lang: str,
                 source_lang: str = 'auto',
                 use_cache: bool = True) -> Dict[str, Any]:
        """
        Translate text to target language.
        
        Args:
            text: Text to translate
            target_lang: Target language code
            source_lang: Source language code (auto-detect if 'auto')
            use_cache: Whether to use translation cache
            
        Returns:
            Dict with translation results
        """
        
        if not text or not text.strip():
            return {
                'success': False,
                'error': 'Empty text provided',
                'original_text': text,
                'translated_text': '',
                'target_language': target_lang
            }
        
        # Normalize language codes
        source_lang = self._normalize_language_code(source_lang)
        target_lang = self._normalize_language_code(target_lang)
        
        # Check cache
        cache_key = f"{source_lang}:{target_lang}:{hash(text)}"
        if use_cache and cache_key in self.cache:
            cached_result = self.cache[cache_key].copy()
            cached_result['from_cache'] = True
            self.logger.info(f"Translation found in cache")
            return cached_result
        
        # Handle long text by chunking
        if len(text) > self.max_text_length:
            return self._translate_long_text(text, source_lang, target_lang, use_cache)
        
        # Try each provider in order
        for i, provider in enumerate(self.providers):
            try:
                # Rate limiting
                self._apply_rate_limit(provider.provider_name)
                
                # Attempt translation
                success, translated_text, error = provider.translate(
                    text, source_lang, target_lang
                )
                
                if success and translated_text:
                    result = {
                        'success': True,
                        'original_text': text,
                        'translated_text': translated_text,
                        'source_language': source_lang,
                        'target_language': target_lang,
                        'provider': provider.provider_name,
                        'provider_index': i,
                        'from_cache': False,
                        'text_length': len(text),
                        'translation_length': len(translated_text)
                    }
                    
                    # Cache successful translation
                    if use_cache:
                        self._add_to_cache(cache_key, result)
                    
                    self.logger.info(f"Translation successful with {provider.provider_name}")
                    return result
                else:
                    self.logger.warning(f"Provider {provider.provider_name} failed: {error}")
                    
            except Exception as e:
                self.logger.error(f"Error with provider {provider.provider_name}: {str(e)}")
                continue
        
        # All providers failed
        return {
            'success': False,
            'error': 'All translation providers failed',
            'original_text': text,
            'translated_text': '',
            'target_language': target_lang,
            'attempted_providers': len(self.providers)
        }
    
    def _translate_long_text(self, 
                            text: str, 
                            source_lang: str, 
                            target_lang: str,
                            use_cache: bool) -> Dict[str, Any]:
        """Translate long text by chunking."""
        
        chunks = self._split_text_into_chunks(text)
        translated_chunks = []
        provider_used = None
        
        self.logger.info(f"Translating long text in {len(chunks)} chunks")
        
        for i, chunk in enumerate(chunks):
            chunk_result = self.translate(
                chunk, 
                target_lang, 
                source_lang, 
                use_cache
            )
            
            if chunk_result['success']:
                translated_chunks.append(chunk_result['translated_text'])
                if not provider_used:
                    provider_used = chunk_result.get('provider')
            else:
                # If any chunk fails, return failure
                return {
                    'success': False,
                    'error': f"Failed to translate chunk {i+1}/{len(chunks)}",
                    'original_text': text,
                    'translated_text': ' '.join(translated_chunks),
                    'target_language': target_lang,
                    'chunks_completed': i
                }
        
        # Combine translated chunks
        translated_text = ' '.join(translated_chunks)
        
        return {
            'success': True,
            'original_text': text,
            'translated_text': translated_text,
            'source_language': source_lang,
            'target_language': target_lang,
            'provider': provider_used,
            'from_cache': False,
            'text_length': len(text),
            'translation_length': len(translated_text),
            'chunks': len(chunks)
        }
    
    def _split_text_into_chunks(self, text: str) -> List[str]:
        """Split text into chunks for translation."""
        
        if len(text) <= self.max_text_length:
            return [text]
        
        chunks = []
        chunk_size = self.max_text_length - self.chunk_overlap
        
        # Try to split on sentence boundaries
        sentences = text.replace('! ', '!|').replace('. ', '.|').replace('? ', '?|').split('|')
        
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            sentence_length = len(sentence)
            
            if current_length + sentence_length > chunk_size and current_chunk:
                # Save current chunk
                chunks.append(' '.join(current_chunk))
                # Start new chunk with overlap
                current_chunk = [sentence]
                current_length = sentence_length
            else:
                current_chunk.append(sentence)
                current_length += sentence_length
        
        # Add remaining chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def detect_language(self, text: str) -> Dict[str, Any]:
        """Detect language of text."""
        
        for provider in self.providers:
            try:
                success, lang_code, confidence = provider.detect_language(text)
                
                if success:
                    return {
                        'success': True,
                        'language': lang_code,
                        'confidence': confidence,
                        'provider': provider.provider_name
                    }
            except Exception as e:
                self.logger.warning(f"Language detection failed with {provider.provider_name}: {str(e)}")
                continue
        
        return {
            'success': False,
            'error': 'Language detection failed with all providers',
            'language': 'unknown',
            'confidence': 0.0
        }
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get combined supported languages from all providers."""
        
        all_languages = {}
        
        for provider in self.providers:
            try:
                languages = provider.get_supported_languages()
                all_languages.update(languages)
            except Exception as e:
                self.logger.warning(f"Failed to get languages from {provider.provider_name}: {str(e)}")
        
        # Add common languages if empty
        if not all_languages:
            all_languages = {
                'en': 'English',
                'es': 'Spanish',
                'fr': 'French',
                'de': 'German',
                'it': 'Italian',
                'pt': 'Portuguese',
                'ru': 'Russian',
                'ja': 'Japanese',
                'ko': 'Korean',
                'zh-cn': 'Chinese (Simplified)',
                'ar': 'Arabic',
                'hi': 'Hindi'
            }
        
        return all_languages
    
    def _normalize_language_code(self, lang_code: str) -> str:
        """Normalize language codes for consistency."""
        
        if not lang_code:
            return 'auto'
        
        lang_code = lang_code.lower().strip()
        
        # Check mapping
        if lang_code in self.LANGUAGE_CODE_MAP:
            return self.LANGUAGE_CODE_MAP[lang_code]
        
        return lang_code
    
    def _apply_rate_limit(self, provider_name: str):
        """Apply rate limiting for API calls."""
        
        current_time = time.time()
        
        if provider_name in self.last_request_time:
            elapsed = current_time - self.last_request_time[provider_name]
            
            if elapsed < self.min_request_interval:
                sleep_time = self.min_request_interval - elapsed
                time.sleep(sleep_time)
        
        self.last_request_time[provider_name] = time.time()
    
    def _add_to_cache(self, key: str, result: Dict[str, Any]):
        """Add translation to cache with size limit."""
        
        # Simple FIFO cache management
        if len(self.cache) >= self.cache_max_size:
            # Remove oldest entry
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        
        self.cache[key] = result.copy()
    
    def clear_cache(self):
        """Clear translation cache."""
        self.cache.clear()
        self.logger.info("Translation cache cleared")
    
    def get_provider_status(self) -> List[Dict[str, Any]]:
        """Get status of all providers."""
        
        status = []
        
        for i, provider in enumerate(self.providers):
            status.append({
                'index': i,
                'name': provider.provider_name,
                'available': True,
                'priority': i + 1
            })
        
        return status
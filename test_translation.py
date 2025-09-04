#!/usr/bin/env python3
"""
Test script for TranslationService functionality.
"""

import os
import sys
import time
from config import Config
from utils.translation_service import TranslationService

def test_translation_service():
    """Test the translation service with multiple languages."""
    
    print("🌐 Testing Translation Service")
    print("=" * 60)
    
    try:
        # Initialize
        config = Config()
        translation_service = TranslationService(config)
        
        print(f"✓ TranslationService initialized")
        
        # Show provider status
        providers = translation_service.get_provider_status()
        print(f"\n📡 Available Providers ({len(providers)}):")
        for provider in providers:
            print(f"  {provider['priority']}. {provider['name']} - {'✓' if provider['available'] else '❌'}")
        
        # Get supported languages
        languages = translation_service.get_supported_languages()
        print(f"\n🌍 Supported Languages: {len(languages)} languages")
        sample_langs = list(languages.items())[:8]
        for code, name in sample_langs:
            print(f"  {code}: {name}")
        if len(languages) > 8:
            print(f"  ... and {len(languages) - 8} more")
        
        # Test texts in different languages
        test_cases = [
            {
                'text': "Hello, this is a test of the translation system.",
                'source': 'en',
                'targets': ['es', 'fr', 'de', 'ja', 'zh-cn', 'ar'],
                'description': 'English to multiple languages'
            },
            {
                'text': "La inteligencia artificial está cambiando el mundo.",
                'source': 'es',
                'targets': ['en', 'fr', 'pt'],
                'description': 'Spanish to other languages'
            },
            {
                'text': "Bonjour le monde! Comment allez-vous aujourd'hui?",
                'source': 'fr',
                'targets': ['en', 'es', 'it'],
                'description': 'French to other languages'
            }
        ]
        
        print("\n" + "=" * 60)
        print("📝 TRANSLATION TESTS")
        print("=" * 60)
        
        all_successful = True
        translation_count = 0
        total_time = 0
        
        for test_num, test_case in enumerate(test_cases, 1):
            print(f"\n🧪 Test {test_num}: {test_case['description']}")
            print(f"📄 Original ({test_case['source']}): \"{test_case['text']}\"")
            print(f"🎯 Translating to {len(test_case['targets'])} languages...")
            
            for target_lang in test_case['targets']:
                start_time = time.time()
                
                result = translation_service.translate(
                    text=test_case['text'],
                    target_lang=target_lang,
                    source_lang=test_case['source']
                )
                
                elapsed = time.time() - start_time
                total_time += elapsed
                
                if result['success']:
                    translation_count += 1
                    translated = result['translated_text']
                    provider = result.get('provider', 'unknown')
                    cached = "📦" if result.get('from_cache') else "🔄"
                    
                    # Truncate long translations for display
                    if len(translated) > 100:
                        display_text = translated[:97] + "..."
                    else:
                        display_text = translated
                    
                    lang_name = languages.get(target_lang, target_lang)
                    print(f"  ✓ {lang_name:15} {cached}: \"{display_text}\"")
                    print(f"    Provider: {provider}, Time: {elapsed:.2f}s")
                else:
                    all_successful = False
                    error = result.get('error', 'Unknown error')
                    print(f"  ❌ {target_lang}: {error}")
        
        # Test language detection
        print("\n" + "=" * 60)
        print("🔍 LANGUAGE DETECTION TESTS")
        print("=" * 60)
        
        detection_tests = [
            ("Hello world", "en"),
            ("Hola mundo", "es"),
            ("Bonjour le monde", "fr"),
            ("Hallo Welt", "de"),
            ("Ciao mondo", "it"),
            ("Olá mundo", "pt"),
            ("Привет мир", "ru"),
            ("こんにちは世界", "ja"),
            ("你好世界", "zh-cn"),
            ("مرحبا بالعالم", "ar")
        ]
        
        detection_success = 0
        
        for text, expected_lang in detection_tests:
            result = translation_service.detect_language(text)
            
            if result['success']:
                detected = result['language']
                confidence = result.get('confidence', 0)
                provider = result.get('provider', 'unknown')
                
                # Check if detection is correct (allowing variants like zh vs zh-cn)
                is_correct = detected.startswith(expected_lang[:2]) or expected_lang.startswith(detected[:2])
                symbol = "✓" if is_correct else "⚠️"
                
                print(f"  {symbol} \"{text[:20]}...\" → {detected} (expected: {expected_lang})")
                
                if confidence is not None and confidence > 0:
                    print(f"    Confidence: {confidence:.2f}, Provider: {provider}")
                
                if is_correct:
                    detection_success += 1
            else:
                print(f"  ❌ \"{text[:20]}...\" → Detection failed")
        
        detection_accuracy = (detection_success / len(detection_tests)) * 100 if detection_tests else 0
        
        # Test long text translation (chunking)
        print("\n" + "=" * 60)
        print("📜 LONG TEXT TRANSLATION TEST")
        print("=" * 60)
        
        long_text = """
        Artificial intelligence has become one of the most transformative technologies of our time.
        From natural language processing to computer vision, AI is revolutionizing how we interact
        with technology. Machine learning models are now capable of understanding context, generating
        creative content, and solving complex problems that were once thought to be exclusively human
        domains. The rapid advancement in deep learning, particularly with transformer architectures,
        has led to breakthrough applications in translation, summarization, and conversational AI.
        As we continue to push the boundaries of what's possible, it's crucial to consider the ethical
        implications and ensure that these powerful tools are developed and deployed responsibly.
        """ * 3  # Repeat to make it longer
        
        print(f"📝 Original text length: {len(long_text)} characters")
        print(f"🎯 Translating to Spanish...")
        
        long_start = time.time()
        long_result = translation_service.translate(
            text=long_text,
            target_lang='es',
            source_lang='en'
        )
        long_elapsed = time.time() - long_start
        
        if long_result['success']:
            translated_length = len(long_result['translated_text'])
            chunks = long_result.get('chunks', 1)
            print(f"✓ Translation successful!")
            print(f"  Translated length: {translated_length} characters")
            print(f"  Chunks processed: {chunks}")
            print(f"  Time: {long_elapsed:.2f}s")
            print(f"  Preview: \"{long_result['translated_text'][:150]}...\"")
        else:
            print(f"❌ Long text translation failed: {long_result.get('error')}")
        
        # Cache testing
        print("\n" + "=" * 60)
        print("💾 CACHE PERFORMANCE TEST")
        print("=" * 60)
        
        cache_test_text = "This is a cache test."
        
        # First translation (not cached)
        start1 = time.time()
        result1 = translation_service.translate(cache_test_text, 'es', 'en')
        time1 = time.time() - start1
        
        # Second translation (should be cached)
        start2 = time.time()
        result2 = translation_service.translate(cache_test_text, 'es', 'en')
        time2 = time.time() - start2
        
        if result1['success'] and result2['success']:
            cached1 = "cached" if result1.get('from_cache') else "not cached"
            cached2 = "cached" if result2.get('from_cache') else "not cached"
            speedup = time1 / time2 if time2 > 0 else 0
            
            print(f"  First call:  {time1:.3f}s ({cached1})")
            print(f"  Second call: {time2:.3f}s ({cached2})")
            print(f"  Cache speedup: {speedup:.1f}x faster")
            
            if result2.get('from_cache'):
                print(f"  ✓ Cache is working correctly!")
            else:
                print(f"  ⚠️ Cache might not be working")
        
        # Clear cache
        translation_service.clear_cache()
        print(f"  ✓ Cache cleared")
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        avg_time = total_time / translation_count if translation_count > 0 else 0
        
        print(f"  Total translations: {translation_count}")
        print(f"  Average time per translation: {avg_time:.2f}s")
        print(f"  Language detection accuracy: {detection_accuracy:.1f}%")
        print(f"  All tests passed: {'✅ Yes' if all_successful else '❌ No'}")
        
        # Provider fallback test
        print("\n" + "=" * 60)
        print("🔄 PROVIDER FALLBACK TEST")
        print("=" * 60)
        
        # This will test fallback by trying a translation
        fallback_result = translation_service.translate(
            "Test fallback mechanism",
            target_lang='es',
            source_lang='en'
        )
        
        if fallback_result['success']:
            provider_index = fallback_result.get('provider_index', -1)
            provider_name = fallback_result.get('provider', 'unknown')
            print(f"  ✓ Translation succeeded with provider #{provider_index + 1}: {provider_name}")
            
            if provider_index > 0:
                print(f"  ℹ️ Fallback occurred - using backup provider")
        else:
            print(f"  ❌ All providers failed")
        
        print("\n✅ Translation service tests completed!")
        return all_successful
        
    except Exception as e:
        print(f"\n❌ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_translation_service()
    sys.exit(0 if success else 1)
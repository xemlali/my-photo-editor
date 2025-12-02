import streamlit as st
import time

# --- فحص المكتبات ---
try:
    from newspaper import Article
    import requests
    import base64
    import google.generativeai as genai
    from PIL import Image, ImageEnhance, ImageOps
    import io
    import re
    import numpy as np
except ImportError as e:
    st.error(f"❌ مكتبة ناقصة: {e}")
    st.stop()

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Editor Pro 9.0 (Multi-Paragraphs)", layout="wide", page_icon="📝")

# --- 2. القائمة الجانبية ---
with st.sidebar:
    st.header("1. البيانات")
    api_key = st.text_input("مفتاح Gemini API", type="password")
    wp_url = st.text_input("رابط الموقع", "https://driouchcity.com")
    wp_user = st.text_input("اسم المستخدم")
    wp_password = st.text_input("كلمة مرور التطبيق", type="password")
    
    st.divider()
    st.header("2. إعدادات المحتوى")
    target_language = st.selectbox(
        "لغة المقال:",
        ["العربية", "الإسبانية (Spanish)", "الفرنسية (French)", "الإنجليزية (English)", "الهولندية (Dutch)", "الألمانية (German)"]
    )
    
    st.divider()
    st.header("3. هندسة الصورة")
    crop_logo = st.checkbox("قص الشريط السفلي (اللوغو)", value=True)
    logo_ratio = st.slider("نسبة القص", 0.0, 0.25, 0.12, step=0.01)
    apply_mirror = st.checkbox("قلب الصورة (Mirror)", value=True)
    red_factor = st.slider("لمسة اللون الأحمر", 0.0, 0.3, 0.08, step=0.01)

# --- 3. الدوال ---

def clean_final_text(text):
    if not text: return ""
    text = text.replace("###SPLIT###", "")
    text = text.replace("###", "").replace("##", "").replace("#", "")
    text = text.replace("**", "").replace("*", "")
    text = text.replace("العنوان:", "").replace("المتن:", "")
    return text.strip()

def resize_fixed_768(image):
    target_w, target_h = 768, 432
    current_w, current_h = image.size
    target_ratio = target_w / target_h
    current_ratio = current_w / current_h
    
    if current_ratio > target_ratio:
        new_h = target_h
        new_w = int(new_h * current_ratio)
        img = image.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target_w) // 2
        img = img.crop((left, 0, left + target_w, target_h))
    else:
        new_w = target_w
        new_h = int(new_w / current_ratio)
        img = image.resize((new_w, new_h), Image.LANCZOS)
        top = (new_h - target_h) // 2
        img = img.crop((0, top, target_w, top + target_h))
    return img

def process_img_pro(source, is_url, do_crop, crop_amount, do_mirror, red_val):
    try:
        if is_url:
            resp = requests.get(source, stream=True, timeout=10)
            img = Image.open(resp.raw)
        else:
            img = Image.open(source)
            
        if img.mode != 'RGB':
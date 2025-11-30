import streamlit as st
import numpy as np
from PIL import Image
from sklearn.cluster import KMeans
import colorsys
import json  # 修复了之前的 NameError

# ==========================================
# 1. 核心算法 (升级版)
# ==========================================

def hex_to_rgb(hex_code):
    h = hex_code.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
    return '#{:02x}{:02x}{:02x}'.format(*rgb)

def extract_smart_colors(image, n_colors=7, min_sat=0.1, min_val=0.1):
    """
    智能提取：
    1. 转为 HSV 空间
    2. 根据阈值剔除 低饱和度(灰/白) 和 低亮度(黑) 的像素
    3. 对剩余的鲜艳像素进行聚类
    """
    # 缩放以加速
    img_small = image.resize((200, 200)) 
    ar = np.asarray(img_small)
    
    # 丢弃 Alpha 通道
    if len(ar.shape) == 3 and ar.shape[2] > 3:
        ar = ar[:, :, :3]
    
    # 展平
    ar = ar.reshape(-1, 3)
    
    # --- 智能过滤核心 ---
    # 将 RGB 归一化到 0-1 并转 HSV
    # 向量化计算有点复杂，这里用列表推导式做预筛选 (为了代码稳健性)
    valid_pixels = []
    
    # 为了速度，随机采样 5000 个像素进行判断，而不是全部
    if len(ar) > 5000:
        indices = np.random.choice(len(ar), 5000, replace=False)
        sample_ar = ar[indices]
    else:
        sample_ar = ar

    for pixel in sample_ar:
        r, g, b = pixel
        h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
        # 过滤掉 饱和度 < min_sat (去除灰/白) 或 亮度 < min_val (去除黑)
        if s >= min_sat and v >= min_val:
            valid_pixels.append(pixel)
    
    # 如果过滤完没剩多少颜色（比如是一张全黑白的图），就回退到原始数据
    if len(valid_pixels) < n_colors:
        valid_pixels = sample_ar
    
    valid_pixels = np.array(valid_pixels)

    # --- K-Means 聚类 ---
    kmeans = KMeans(n_clusters=n_colors, n_init=5, max_iter=200)
    kmeans.fit(valid_pixels)
    colors = kmeans.cluster_centers_
    
    return [rgb_to_hex(tuple(map(int, c))) for c in colors]

def sort_palette(hex_colors, mode):
    """快速排序工具"""
    rgb_colors = [hex_to_rgb(c) for c in hex_colors]
    
    if mode == "brightness_asc": # 暗 -> 亮
        rgb_sorted = sorted(rgb_colors, key=lambda c: c[0]*0.299 + c[1]*0.587 + c[2]*0.114)
    elif mode == "brightness_desc": # 亮 -> 暗
        rgb_sorted = sorted(rgb_colors, key=lambda c: c[0]*0.299 + c[1]*0.587 + c[2]*0.114, reverse=True)
    elif mode == "hue": # 色相排序 (彩虹)
        rgb_sorted = sorted(rgb_colors, key=lambda c: colorsys.rgb_to_hsv(c[0]/255, c[1]/255, c[2]/255)[0])
    elif mode == "reverse":
        return hex_colors[::-1]
    else:
        return hex_colors

    return [rgb_to_hex(c) for c in rgb_sorted]

def generate_clr(hex_colors):
    content = ""
    for idx, hex_code in enumerate(hex_colors):
        r, g, b = hex_to_rgb(hex_code)
        content += f"{idx + 1} {r} {g} {b}\n"
    return content

# ==========================================
# 2. 状态管理
# ==========================================
if 'palette' not in st.session_state:
    st.session_state.palette = []
if 'img_key' not in st.session_state:
    st.session_state.img_key = None

def update_color(idx, new_color):
    st.session_state.palette[idx] = new_color

def remove_color(idx):
    st.session_state.palette.pop(idx)

# ==========================================
# 3. 页面 UI
# ==========================================
st.set_page_config(page_title="GIS Smart Palette", page_icon="🎨", layout="wide")

st.markdown("""
<style>
    /* 样式微调：让预览条更好看 */
    .preview-bar {
        width: 100%; height: 80px; border-radius: 12px; margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 2px solid #fff;
    }
    /* 紧凑的控制区 */
    .control-area { background-color: #f7f9fc; padding: 15px; border-radius: 10px; margin-bottom: 20px;}
</style>
""", unsafe_allow_html=True)

st.title("🎨 GIS 智能色带提取器")

# --- 侧边栏：上传与提取参数 ---
with st.sidebar:
    st.header("1. 上传与提取")
    uploaded_file = st.file_uploader("上传图片 (电影截图 / 色卡图)", type=['jpg', 'png', 'jpeg'])
    
    st.divider()
    st.subheader("🧪 智能提取参数")
    st.info("👇 调整这里可以防止提取出黑色/灰色背景")
    
    n_colors = st.slider("提取颜色数量", 3, 12, 6)
    min_sat = st.slider("最低饱和度 (去除灰/白)", 0.0, 1.0, 0.2, help="值越大，越只保留鲜艳颜色")
    min_val = st.slider("最低亮度 (去除黑色)", 0.0, 1.0, 0.2, help="值越大，越只保留明亮颜色")
    
    extract_btn = st.button("🚀 重新提取", type="primary", use_container_width=True)

# --- 主逻辑处理 ---
if uploaded_file:
    # 检查是否需要运行提取
    file_id = f"{uploaded_file.name}-{n_colors}-{min_sat}-{min_val}"
    
    if extract_btn or st.session_state.img_key != file_id:
        image = Image.open(uploaded_file)
        with st.spinner("正在智能分析色彩..."):
            # 运行核心提取算法
            new_colors = extract_smart_colors(image, n_colors, min_sat, min_val)
            # 默认给一个亮度排序，因为乱序的渐变通常不好看
            st.session_state.palette = sort_palette(new_colors, "brightness_asc")
            st.session_state.img_key = file_id

    # 显示原图 (折叠状态，节省空间)
    with st.expander("🖼️ 查看原始图片", expanded=False):
        st.image(uploaded_file, width=400)

# --- 编辑器区域 ---
if st.session_state.palette:
    
    # 1. 顶部：渐变预览
    st.subheader("2. 渐变预览 (Real-time)")
    css = f"linear-gradient(to right, {', '.join(st.session_state.palette)})"
    st.markdown(f'<div class="preview-bar" style="background: {css};"></div>', unsafe_allow_html=True)

    # 2. 中部：快捷操作工具栏 (Smart Actions)
    st.markdown('<div class="control-area">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("✨ 按亮度排序 (暗→亮)", use_container_width=True):
            st.session_state.palette = sort_palette(st.session_state.palette, "brightness_asc")
            st.rerun()
    with c2:
        if st.button("✨ 按色相排序 (彩虹)", use_container_width=True):
            st.session_state.palette = sort_palette(st.session_state.palette, "hue")
            st.rerun()
    with c3:
        if st.button("🔄 顺序反转", use_container_width=True):
            st.session_state.palette = sort_palette(st.session_state.palette, "reverse")
            st.rerun()
    with c4:
        st.caption("👆 点击按钮可快速调整渐变逻辑，无需手动一个个拖拽。")
    st.markdown('</div>', unsafe_allow_html=True)

    # 3. 底部：精细调整 (颜色选择 + 删除)
    st.subheader("3. 颜色微调")
    
    # 动态布局：每行6个
    cols = st.columns(6)
    for i, color in enumerate(st.session_state.palette):
        col = cols[i % 6]
        with col:
            # 颜色选择器 (修改颜色)
            new_val = st.color_picker(f"C{i+1}", color, key=f"cp_{i}", label_visibility="collapsed")
            if new_val != color:
                update_color(i, new_val)
                st.rerun()
            
            # 删除按钮 (红色小垃圾桶)
            if st.button("🗑️", key=f"del_{i}", help="删除此颜色"):
                remove_color(i)
                st.rerun()

    st.divider()

    # 4. 导出
    st.subheader("4. 导出结果")
    d1, d2 = st.columns(2)
    
    base_name = uploaded_file.name.split('.')[0]
    
    with d1:
        st.download_button(
            label="📄 下载 ArcGIS .clr 文件",
            data=generate_clr(st.session_state.palette),
            file_name=f"{base_name}_gradient.clr",
            mime="text/plain",
            type="primary",
            use_container_width=True
        )
    
    with d2:
        # JSON 备份
        json_struct = [{
            "name": base_name,
            "category": "Extracted",
            "colors": st.session_state.palette
        }]
        st.download_button(
            label="📦 下载 JSON 配置",
            data=json.dumps(json_struct, indent=2),
            file_name=f"{base_name}.json",
            mime="application/json",
            use_container_width=True
        )

else:
    st.info("👋 请在左侧上传图片。可以是电影截图，也可以是那种一排颜色的色卡图。")

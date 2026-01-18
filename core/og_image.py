"""
Generate Open Graph images for social sharing.

Creates attractive 1200x630px images for WhatsApp, Twitter, Facebook.
"""

from PIL import Image, ImageDraw, ImageFont
import io
import math
from typing import Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)

# OG Image dimensions (optimal for WhatsApp/Twitter/Facebook)
OG_WIDTH = 1200
OG_HEIGHT = 630

# Colors from visualization - earthy map palette
CLUSTER_COLORS = [
    '#7cb374',  # sage green
    '#c9a66b',  # tan
    '#8fa3bf',  # slate blue
    '#d4a574',  # terracotta
    '#9db4a0',  # muted green
    '#b8a090',  # taupe
    '#a8c0a8',  # soft green
    '#c4b090',  # sand
    '#90a8b8',  # steel blue
    '#b8a8a0',  # warm gray
]


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def get_cluster_color(cluster_id: int) -> Tuple[int, int, int]:
    """Get RGB color for a cluster ID."""
    color_hex = CLUSTER_COLORS[abs(cluster_id) % len(CLUSTER_COLORS)]
    return hex_to_rgb(color_hex)


def darken_color(rgb: Tuple[int, int, int], factor: float = 0.7) -> Tuple[int, int, int]:
    """Darken an RGB color."""
    return tuple(int(c * factor) for c in rgb)


def try_load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Try to load a nice font, fallback to default."""
    font_names = [
        # macOS
        '/System/Library/Fonts/Supplemental/Arial.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
        # Linux
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
    ]
    
    if bold:
        font_names = [
            '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
            '/System/Library/Fonts/Supplemental/Arial.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        ]
    
    for font_path in font_names:
        try:
            return ImageFont.truetype(font_path, size)
        except (OSError, IOError):
            continue
    
    # Fallback to default
    return ImageFont.load_default()


def generate_bubble_map_og_image(
    cluster_name: str,
    cluster_id: int,
    user_cluster_size: int,
    total_clusters: int,
    total_voters: int
) -> io.BytesIO:
    """
    Generate an attractive OG image for sharing bubble map position.
    Styled to match the D3.js visualization aesthetic.
    
    Args:
        cluster_name: Name of the user's cluster
        cluster_id: ID of the user's cluster
        user_cluster_size: Number of people in the cluster
        total_clusters: Total number of clusters
        total_voters: Total number of voters
        
    Returns:
        BytesIO object containing PNG image
    """
    # Create image with map-like gradient background
    img = Image.new('RGB', (OG_WIDTH, OG_HEIGHT), '#f8f5ed')
    draw = ImageDraw.Draw(img)
    
    # Add subtle gradient effect (matching visualization.html)
    for y in range(OG_HEIGHT):
        alpha = y / OG_HEIGHT
        color_start = hex_to_rgb('#f8f5ed')
        color_end = hex_to_rgb('#f0ebe0')
        color = tuple(int(color_start[i] + (color_end[i] - color_start[i]) * alpha) 
                     for i in range(3))
        draw.line([(0, y), (OG_WIDTH, y)], fill=color)
    
    # Add subtle paper texture pattern
    add_paper_texture(draw)
    
    # Draw decorative bubbles in background (map-style)
    draw_map_style_bubbles(draw, cluster_id, total_clusters, user_cluster_size)
    
    # Draw user position marker (pin) over their cluster
    draw_user_position_marker(draw, cluster_id, total_clusters)
    
    # Add header with site branding
    font_header = try_load_font(28, bold=True)
    draw.text((50, 40), "memoria.uy", font=font_header, fill='#000000')
    font_subheader = try_load_font(16, bold=False)
    draw.text((50, 75), "// Mapa de Burbujas", font=font_subheader, fill='#666666')
    
    # Draw main callout box at bottom
    box_y = 420
    box_height = 170
    box_rect = [50, box_y, OG_WIDTH - 50, box_y + box_height]
    
    # Box with cluster color border
    user_color = get_cluster_color(cluster_id)
    draw.rectangle(box_rect, fill=(255, 255, 255, 250), outline=user_color, width=6)
    
    # Cluster name with icon
    font_name = try_load_font(48, bold=True)
    name_y = box_y + 25
    
    # Handle long names
    if len(cluster_name) > 28:
        words = cluster_name.split()
        mid = len(words) // 2
        line1 = ' '.join(words[:mid])
        line2 = ' '.join(words[mid:])
        draw.text((70, name_y), line1, font=font_name, fill='#000000')
        draw.text((70, name_y + 50), line2, font=font_name, fill='#000000')
    else:
        draw.text((70, name_y), cluster_name, font=font_name, fill='#000000')
    
    # Stats bar at bottom of box
    font_stats = try_load_font(22, bold=False)
    stats_y = box_y + box_height - 45
    stats_text = f"👥 {user_cluster_size} personas  •  {total_clusters} burbujas  •  {total_voters} votantes"
    draw.text((70, stats_y), stats_text, font=font_stats, fill='#555555')
    
    # Convert to bytes
    buffer = io.BytesIO()
    img.save(buffer, format='PNG', optimize=True, quality=95)
    buffer.seek(0)
    
    return buffer


def add_paper_texture(draw: ImageDraw):
    """Add subtle paper texture like the CSS pattern."""
    import random
    random.seed(42)
    
    # Add random tiny dots for texture
    for _ in range(200):
        x = random.randint(0, OG_WIDTH)
        y = random.randint(0, OG_HEIGHT)
        size = random.randint(1, 2)
        opacity = random.randint(10, 30)
        color = tuple([200 - opacity] * 3)
        draw.ellipse([x, y, x + size, y + size], fill=color)


def draw_user_position_marker(draw: ImageDraw, cluster_id: int, total_clusters: int):
    """Draw a red location pin marker over the user's cluster."""
    import random
    random.seed(cluster_id)
    
    # Calculate position for this cluster
    angle = (cluster_id % min(total_clusters, 8)) / min(total_clusters, 8) * 2 * math.pi
    radius_from_center = 180
    
    center_x = OG_WIDTH // 2 + int(math.cos(angle) * radius_from_center)
    center_y = 250 + int(math.sin(angle) * radius_from_center)
    
    # Draw location pin (like in the visualization)
    pin_points = [
        (center_x, center_y - 28),  # Top
        (center_x + 10, center_y - 18),  # Right top
        (center_x + 10, center_y - 10),  # Right middle
        (center_x, center_y),  # Bottom point
        (center_x - 10, center_y - 10),  # Left middle
        (center_x - 10, center_y - 18),  # Left top
    ]
    
    # Outer glow
    for r in range(8, 0, -2):
        alpha = int(50 * (1 - r / 8))
        glow_color = (255, 200 + alpha, 150 + alpha)
        draw.ellipse([center_x - r, center_y - r, center_x + r, center_y + r], 
                    fill=glow_color)
    
    # Pin body
    draw.polygon(pin_points, fill='#dc2626', outline='#991b1b')
    
    # Inner white circle
    draw.ellipse([center_x - 4, center_y - 15, center_x + 4, center_y - 7], 
                fill='#ffffff')


def draw_map_style_bubbles(draw: ImageDraw, user_cluster_id: int, total_clusters: int, user_cluster_size: int):
    """Draw bubbles styled like the D3.js map visualization."""
    import random
    random.seed(42)
    
    num_bubbles = min(total_clusters, 8)
    
    for i in range(num_bubbles):
        cluster_id = i
        is_user_cluster = (cluster_id == user_cluster_id % num_bubbles)
        
        # Position bubbles in attractive layout
        angle = (i / num_bubbles) * 2 * math.pi + 0.3
        radius_from_center = 180 + random.randint(-30, 30)
        
        center_x = OG_WIDTH // 2 + int(math.cos(angle) * radius_from_center)
        center_y = 250 + int(math.sin(angle) * radius_from_center)
        
        # Bubble size - user cluster is bigger
        if is_user_cluster:
            bubble_radius = 85
        else:
            bubble_radius = 55 + random.randint(-10, 15)
        
        color = get_cluster_color(cluster_id)
        
        # Draw bubble with gradient effect (from center outward)
        for r in range(bubble_radius, 0, -3):
            # Create radial gradient effect
            alpha = r / bubble_radius
            lighter_color = tuple(
                min(255, int(c + (255 - c) * (1 - alpha) * 0.4)) 
                for c in color
            )
            draw.ellipse(
                [center_x - r, center_y - r, center_x + r, center_y + r],
                fill=lighter_color
            )
        
        # Draw stroke
        stroke_color = darken_color(color, 0.7)
        stroke_width = 4 if is_user_cluster else 2
        draw.ellipse(
            [center_x - bubble_radius, center_y - bubble_radius,
             center_x + bubble_radius, center_y + bubble_radius],
            outline=stroke_color,
            width=stroke_width
        )




def generate_default_og_image() -> io.BytesIO:
    """Generate default OG image for users not in clusters yet."""
    img = Image.new('RGB', (OG_WIDTH, OG_HEIGHT), '#f8f5ed')
    draw = ImageDraw.Draw(img)
    
    # Gradient background
    for y in range(OG_HEIGHT):
        alpha = y / OG_HEIGHT
        color = tuple(int(248 - alpha * 8) for _ in range(3))
        draw.line([(0, y), (OG_WIDTH, y)], fill=color)
    
    # Main text
    font_title = try_load_font(72, bold=True)
    font_subtitle = try_load_font(40, bold=False)
    
    title = "Mapa de Burbujas"
    subtitle = "Descubrí en qué burbuja estás"
    
    # Center text
    try:
        bbox = draw.textbbox((0, 0), title, font=font_title)
        text_width = bbox[2] - bbox[0]
        text_x = (OG_WIDTH - text_width) // 2
    except:
        text_x = 300
    
    draw.text((text_x, 220), title, font=font_title, fill='#000000')
    
    try:
        bbox = draw.textbbox((0, 0), subtitle, font=font_subtitle)
        text_width = bbox[2] - bbox[0]
        text_x = (OG_WIDTH - text_width) // 2
    except:
        text_x = 280
        
    draw.text((text_x, 320), subtitle, font=font_subtitle, fill='#666666')
    
    # Footer
    font_footer = try_load_font(32, bold=False)
    footer = "memoria.uy - Votá noticias uruguayas"
    try:
        bbox = draw.textbbox((0, 0), footer, font=font_footer)
        text_width = bbox[2] - bbox[0]
        text_x = (OG_WIDTH - text_width) // 2
    except:
        text_x = 300
        
    draw.text((text_x, 480), footer, font=font_footer, fill='#999999')
    
    # Convert to bytes
    buffer = io.BytesIO()
    img.save(buffer, format='PNG', optimize=True)
    buffer.seek(0)
    
    return buffer

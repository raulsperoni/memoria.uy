// content.js - Extracts article HTML from the current page

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getArticleData') {
    try {
      const articleData = extractArticleData();
      sendResponse(articleData);
    } catch (error) {
      console.error('Error extracting article data:', error);
      sendResponse({ error: error.message });
    }
  }
  return true;  // Keep channel open for async response
});

function extractArticleData() {
  // Strategy: Try multiple methods to extract the article content
  // 1. Look for <article> tag
  // 2. Look for common article selectors
  // 3. Fallback to entire body HTML

  let articleElement = null;
  let html = '';

  // Method 1: Find <article> tag
  articleElement = document.querySelector('article');

  // Method 2: Try common article container selectors
  if (!articleElement) {
    const selectors = [
      '[role="article"]',
      '.article-content',
      '.article-body',
      '.post-content',
      '.entry-content',
      'main article',
      'main .content',
      '#article',
      '#content',
      '.story-body',
      '.article__body',
      '.content-body'
    ];

    for (const selector of selectors) {
      articleElement = document.querySelector(selector);
      if (articleElement) break;
    }
  }

  // Method 3: Try finding main content by heuristics
  // Look for largest text block near an H1
  if (!articleElement) {
    const h1 = document.querySelector('h1');
    if (h1) {
      let parent = h1.parentElement;
      let attempts = 0;

      // Walk up the DOM tree looking for a good container
      while (parent && attempts < 5) {
        const textLength = parent.textContent.length;
        const paragraphs = parent.querySelectorAll('p').length;

        // Good article container has significant text and paragraphs
        if (textLength > 500 && paragraphs > 3) {
          articleElement = parent;
          break;
        }

        parent = parent.parentElement;
        attempts++;
      }
    }
  }

  // Method 4: Fallback to body (cleaned)
  if (!articleElement) {
    articleElement = document.body;
  }

  // Clone the element to avoid modifying the page
  const clone = articleElement.cloneNode(true);

  // Clean up: Remove scripts, styles, ads, etc.
  cleanElement(clone);

  // Get the HTML
  html = clone.innerHTML;

  // Also include metadata
  const metadata = extractMetadata();

  return {
    html: html,
    metadata: metadata,
    selector: getElementSelector(articleElement),
    timestamp: new Date().toISOString()
  };
}

function cleanElement(element) {
  // Remove unwanted elements
  const unwantedSelectors = [
    'script',
    'style',
    'iframe',
    'noscript',
    '.ad',
    '.advertisement',
    '.social-share',
    '.comments',
    '.related-articles',
    '[class*="paywall"]',
    '[id*="paywall"]'
  ];

  unwantedSelectors.forEach(selector => {
    element.querySelectorAll(selector).forEach(el => el.remove());
  });

  // Remove inline event handlers
  element.querySelectorAll('*').forEach(el => {
    Array.from(el.attributes).forEach(attr => {
      if (attr.name.startsWith('on')) {
        el.removeAttribute(attr.name);
      }
    });
  });
}

function extractMetadata() {
  const metadata = {
    title: document.title,
    url: window.location.href,
    og: {},
    twitter: {},
    jsonLd: []
  };

  // Extract Open Graph tags
  document.querySelectorAll('meta[property^="og:"]').forEach(meta => {
    const property = meta.getAttribute('property').replace('og:', '');
    metadata.og[property] = meta.getAttribute('content');
  });

  // Extract Twitter Card tags
  document.querySelectorAll('meta[name^="twitter:"]').forEach(meta => {
    const name = meta.getAttribute('name').replace('twitter:', '');
    metadata.twitter[name] = meta.getAttribute('content');
  });

  // Extract JSON-LD structured data
  document.querySelectorAll('script[type="application/ld+json"]').forEach(script => {
    try {
      const data = JSON.parse(script.textContent);
      metadata.jsonLd.push(data);
    } catch (e) {
      // Invalid JSON, skip
    }
  });

  // Extract basic meta tags
  const metaTags = ['description', 'author', 'keywords', 'published_time'];
  metaTags.forEach(name => {
    const meta = document.querySelector(`meta[name="${name}"]`);
    if (meta) {
      metadata[name] = meta.getAttribute('content');
    }
  });

  return metadata;
}

function getElementSelector(element) {
  // Generate a CSS selector path for debugging
  if (element.id) {
    return `#${element.id}`;
  }

  if (element.className) {
    const classes = Array.from(element.classList).join('.');
    return `${element.tagName.toLowerCase()}.${classes}`;
  }

  return element.tagName.toLowerCase();
}

// Optional: Highlight the extracted content when extension is activated
function highlightExtractedContent() {
  const article = document.querySelector('article') ||
                  document.querySelector('[role="article"]');

  if (article) {
    article.style.outline = '3px solid #2563eb';
    article.style.outlineOffset = '4px';

    setTimeout(() => {
      article.style.outline = '';
      article.style.outlineOffset = '';
    }, 2000);
  }
}

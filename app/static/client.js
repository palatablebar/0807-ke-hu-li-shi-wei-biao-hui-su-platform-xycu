export async function request(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const error = new Error(body.message || `请求失败 · ${response.status}`);
    error.code = body.code;
    throw error;
  }
  return response.json();
}

export function element(tag, text, attrs = {}) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
  return node;
}

export function pretty(value) {
  return value !== null && typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value ?? '—');
}

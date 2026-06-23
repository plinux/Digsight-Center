export function setText(element, text) {
  element.textContent = text;
}

export function createButton(label, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.addEventListener("click", onClick);
  return button;
}

export function labeledInput(text, type, value, attrs = {}) {
  const label = document.createElement("label");
  label.textContent = text;
  const input = document.createElement("input");
  input.type = type;
  input.value = value;
  for (const [key, attrValue] of Object.entries(attrs)) {
    if (attrValue === false || attrValue === null || attrValue === undefined) {
      continue;
    }
    input.setAttribute(key, attrValue === true ? "" : attrValue);
  }
  label.append(input);
  return {label, input};
}

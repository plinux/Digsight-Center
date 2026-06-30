function verticalRatioFromPointer(element, event) {
  const rect = element.getBoundingClientRect();
  if (!rect.height) {
    return 0;
  }
  return Math.max(0, Math.min(1, (rect.bottom - event.clientY) / rect.height));
}

export function verticalValueFromPointer(element, event, maxValue, normalizeValue) {
  const ratio = verticalRatioFromPointer(element, event);
  return normalizeValue(ratio * maxValue);
}

export function bindVerticalSlider(element, options) {
  const normalizeValue = options.normalizeValue || ((value) => value);
  const keySteps = options.keySteps || {};
  const maxValue = () => Number(typeof options.maxValue === "function" ? options.maxValue() : options.maxValue);
  const currentValue = () => normalizeValue(options.currentValue?.() ?? 0);
  let isDragging = false;

  const updateFromPointer = (event, commit = false) => {
    const nextValue = verticalValueFromPointer(element, event, maxValue(), normalizeValue);
    if (commit) {
      options.onCommit?.(nextValue);
      return;
    }
    options.onPreview?.(nextValue);
  };

  element.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    options.onPointerDown?.(event);
    element.focus({preventScroll: true});
    isDragging = true;
    element.setPointerCapture?.(event.pointerId);
    updateFromPointer(event);
  });
  element.addEventListener("pointermove", (event) => {
    if (!isDragging) {
      return;
    }
    event.preventDefault();
    updateFromPointer(event);
  });
  element.addEventListener("pointerup", (event) => {
    if (!isDragging) {
      return;
    }
    event.preventDefault();
    isDragging = false;
    element.releasePointerCapture?.(event.pointerId);
    updateFromPointer(event, true);
  });
  element.addEventListener("pointercancel", (event) => {
    if (!isDragging) {
      return;
    }
    isDragging = false;
    element.releasePointerCapture?.(event.pointerId);
    options.onCommit?.(currentValue());
  });
  element.addEventListener("keydown", (event) => {
    if (event.key === "Home") {
      event.preventDefault();
      event.stopPropagation();
      options.onCommit?.(normalizeValue(options.homeValue ?? 0));
      return;
    }
    if (event.key === "End") {
      event.preventDefault();
      event.stopPropagation();
      options.onCommit?.(normalizeValue(options.endValue ?? maxValue()));
      return;
    }
    if (!(event.key in keySteps)) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    options.onCommit?.(normalizeValue(currentValue() + keySteps[event.key]));
  });
}

export function setVerticalSliderFill(element, cssVariableName, percent, ariaValue, ariaText = "") {
  const safePercent = Math.max(0, Math.min(100, Number(percent) || 0));
  element.style.setProperty(cssVariableName, `${Math.round(safePercent * 10) / 10}%`);
  element.setAttribute("aria-valuenow", String(ariaValue));
  if (ariaText) {
    element.setAttribute("aria-valuetext", ariaText);
  } else {
    element.removeAttribute("aria-valuetext");
  }
}

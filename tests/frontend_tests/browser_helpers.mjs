async function evaluateWith(target, expression) {
  if (typeof target === "function") {
    return await target(expression);
  }
  return await target.evaluate(expression);
}

export async function nextFrame(target) {
  return await evaluateWith(target, "new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))))");
}

export async function getBox(target, selector, options = {}) {
  const expression = `(() => {
    const node = document.querySelector(${JSON.stringify(selector)});
    if (!node) {
      return null;
    }
    if (${options.scrollIntoView ? "true" : "false"}) {
      node.scrollIntoView({block: "center", inline: "center"});
    }
    const rect = node.getBoundingClientRect();
    return {
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height / 2,
      left: rect.left,
      right: rect.right,
      top: rect.top,
      bottom: rect.bottom,
      width: rect.width,
      height: rect.height
    };
  })()`;
  return await evaluateWith(target, expression);
}

export async function assertCentered(target, outerSelector, innerSelector, tolerance = 2) {
  const outer = await getBox(target, outerSelector);
  const inner = await getBox(target, innerSelector);
  if (!outer || !inner) {
    throw new Error(`${innerSelector} or ${outerSelector} is missing`);
  }
  const outerCenterX = (outer.left + outer.right) / 2;
  const innerCenterX = (inner.left + inner.right) / 2;
  const outerCenterY = (outer.top + outer.bottom) / 2;
  const innerCenterY = (inner.top + inner.bottom) / 2;
  if (Math.abs(outerCenterX - innerCenterX) > tolerance || Math.abs(outerCenterY - innerCenterY) > tolerance) {
    throw new Error(`${innerSelector} is not centered in ${outerSelector}`);
  }
}

export function assertNamedChecks(scope, assertions, details = {}) {
  const failed = assertions.filter(([, ok]) => !ok);
  if (failed.length) {
    throw new Error(`${scope} failed: ${failed.map(([name]) => name).join(", ")}\n${JSON.stringify(details, null, 2)}`);
  }
}

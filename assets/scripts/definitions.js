document.addEventListener("DOMContentLoaded", function () {
  const defs = document.getElementsByClassName("definition")
  for (const d of defs) {
    const id = d.id
    const re = new RegExp(d.dataset.re, d.dataset.flags)
    const paras = document.querySelectorAll(`#${id} ~ p`)
    paras.forEach((p) => replaceInTextNodes(p, re, id))
  }
})

function replaceInTextNodes(node, re, id) {
  // Walk text nodes only — never touch element nodes (math spans, etc.)
  for (const child of [...node.childNodes]) {
    if (child.nodeType === Node.TEXT_NODE) {
      const text = child.textContent
      if (!re.test(text)) continue
      re.lastIndex = 0
      // Split text on matches and rebuild as a fragment
      const frag = document.createDocumentFragment()
      let last = 0
      let m
      re.lastIndex = 0
      while ((m = re.exec(text)) !== null) {
        if (m.index > last) {
          frag.appendChild(document.createTextNode(text.slice(last, m.index)))
        }
        const a = document.createElement("a")
        a.href = `#${id}`
        a.className = "quarto-xref def-link"
        a.setAttribute("aria-expanded", "false")
        a.textContent = m[0]
        frag.appendChild(a)
        last = m.index + m[0].length
      }
      if (last < text.length) {
        frag.appendChild(document.createTextNode(text.slice(last)))
      }
      node.replaceChild(frag, child)
    } else if (child.nodeType === Node.ELEMENT_NODE && child.tagName !== "A") {
      // Recurse into element children but skip existing anchors
      if (!child.classList.contains("math")) {
        replaceInTextNodes(child, re, id)
      }
    }
  }
}

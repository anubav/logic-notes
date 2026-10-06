document.addEventListener("DOMContentLoaded", function () {
  const defs = document.getElementsByClassName("definition")
  for (const d of defs) {
    const id = d.id
    const re = new RegExp(d.dataset.re, d.dataset.flags)
    const paras = document.querySelectorAll(`#${id} ~ p`)
    paras.forEach((p) => walkTextNodes(p, re, id))
  }
})

function walkTextNodes(node, re, id) {
  if (node.nodeType === Node.TEXT_NODE) {
    re.lastIndex = 0
    if (!re.test(node.textContent)) return
    const text = node.textContent
    const frag = document.createDocumentFragment()
    let last = 0
    re.lastIndex = 0
    let m
    while ((m = re.exec(text)) !== null) {
      if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)))
      const a = document.createElement("a")
      a.href = `#${id}`
      a.className = "quarto-xref def-link"
      a.setAttribute("aria-expanded", "false")
      a.textContent = m[0]
      frag.appendChild(a)
      last = m.index + m[0].length
      if (m[0].length === 0) re.lastIndex++ // prevent infinite loop on zero-length match
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)))
    node.parentNode.replaceChild(frag, node)
  } else if (node.nodeType === Node.ELEMENT_NODE && node.tagName !== "A" && !node.classList.contains("math")) {
    for (const child of [...node.childNodes]) walkTextNodes(child, re, id)
  }
}

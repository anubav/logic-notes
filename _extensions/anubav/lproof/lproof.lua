quarto.doc.add_html_dependency {
    name = "lproof",
    version = "1.0.0",
    stylesheets = { "lproof.min.css" },
    scripts = { "lproof.js" },
}

local loc = lpeg.locale()
local S = (loc.space - lpeg.P("\n")) ^ 0 -- inline whitespace

local function trimRight(str)
    --[[
        Remove trailing inline whitespace from string
    ]]
    return (S * lpeg.C(lpeg.P(1) ^ 1) / string.reverse):match(string.reverse(str))
end

local function readString(str)
    --[[
        Read a string with all pandoc input options and return generated list of inlines
    ]]
    if str == "" then
        return ""
    else
        doc = pandoc.read(str, "markdown")
        return doc.blocks[1].content
    end
end

local function readStringAsMath(str)
    --[[
        Read a string in implied math-mode with all pandoc input options and return generated list of inlines
    ]]
    if str == "" then
        return ""
    else
        doc = pandoc.read("$" .. str .. "$", "markdown")
        return doc.blocks[1].content
    end
end

local function cleanRef(ref)
    --[[
        Collect end points of reference range and clean whitespace
    ]]
    ref = trimRight(ref)
    local first = ((1 - lpeg.P("--")) ^ 1) / trimRight
    local range = lpeg.Ct(first * "--" * S * (lpeg.P(1) ^ 1 / trimRight))
    local cleaned = range + lpeg.C(lpeg.P(1) ^ 1)
    return cleaned:match(ref)
end

local function numFromIndex(index, proof)
    --[[
        Return the number of the indexed line in proof
    ]]
    for n, proofLine in ipairs(proof) do
        if proofLine["index"] == index then
            return n
        end
    end
    return nil
end

local function refStr(refs)
    --[[
        return a formatted string of all cross-references
    ]]
    local str = ""
    for _, ref in ipairs(refs) do
        if type(ref) == "string" then
            str = str .. ", " .. ref
        else
            str = str .. ", " .. ref[1] .. "\\unicode{x2013}" .. ref[2]
        end
    end
    return string.sub(str, 3, #str) -- omit leading  ", "
end

local function numStr(refs, proof)
    --[[
        return a comma-separated string of all cross-referenced line numbers
    ]]
    local nums = {}
    for _, ref in ipairs(refs) do
        if type(ref) == "string" then
            if numFromIndex(ref, proof) then
                nums[#nums + 1] = numFromIndex(ref, proof)
            else
                return nil
            end
        else
            if numFromIndex(ref[1], proof) and numFromIndex(ref[2], proof) then
                for n = numFromIndex(ref[1], proof), numFromIndex(ref[2], proof) do
                    nums[#nums + 1] = n
                end
            else
                return nil
            end
        end
    end

    local str = ""
    for _, num in ipairs(nums) do
        str = str .. "," .. num
    end
    return string.sub(str, 2, #str) -- omit leading  ","
end

local function crossReference(proof)
    -- Add line numbers to lines in prloc
    local updatedProof = {}
    for n, proofLine in ipairs(proof) do
        proofLine["line"] = n
        if proofLine["refs"] then
            proofLine["crossrefs"] = numStr(proofLine.refs, proof)
            proofLine["refs"] = refStr(proofLine.refs)
        end
        updatedProof[n] = proofLine
    end
    return updatedProof
end

local function proofLineTable(index, depth, hypothesis, formula, justification, refs)
    --[[
        A table representation of a line in a proof
    ]]
    return {
        index = index,
        depth = depth,
        hypothesis = hypothesis,
        formula = formula,
        justification = justification,
        refs = refs
    }
end

local function ellipsesLine()
    --[[
        Return an ellipses proof line
    ]]
    return {
        index = "$\\vdots$",
        depth = 0,
        formula = "",
        justification = "",
        ellipses = true
    }
end

local function parseProof(proofStr)
    --[[
        Parse a text string representing a proof. Return an array of tables, each
        of which represents a line in the proof. The parsed proof can then be sent to ProofToHTML or
        ProofToLaTeX for output specific filtering
    ]]
    -- Sub-patterns for parsing lines in a proof
    local index = S * ((lpeg.P(1) - ".") ^ 1 / trimRight) * "." * S
    local indentMarker = "|" * S
    local depth = (lpeg.C(indentMarker) ^ 1 / function(...) return #{ ... } end) + lpeg.Cc(0)
    local hypothesisMarker = "_" * S
    local hypothesis = (hypothesisMarker / function() return true end) + lpeg.Cc(nil)
    local formula = lpeg.C((lpeg.P(1) - lpeg.S("[\n")) ^ 1) / trimRight
    local ref = (lpeg.P(1) - lpeg.S ",]") ^ 1 / cleanRef
    local refEntries = ":" * S * lpeg.Ct(ref * ("," * S * ref) ^ 0)
    local justification = ("[" * S * ((lpeg.P(1) - lpeg.S ":]") ^ 1 / trimRight) * (refEntries ^ -1) * "]" * S) ^ -1

    -- Pattern for a line in a proof
    local ellipses = S * "..." * S
    local proofLine = index * depth * hypothesis * formula * justification
    proofLine = ((proofLine / proofLineTable) + (ellipses / ellipsesLine)) * (lpeg.P("\n") + -1)

    -- Pattern for a proof
    local proof = lpeg.Ct(proofLine ^ 1)
    local parsedProof = proof:match(proofStr)
    return crossReference(parsedProof)
end

local function proofToHTML(proof)
    --[[
      Create AST elements for HTML rendering of a proof. Proper rendering requires link to
      stylesheet proof.css
    ]]
    local lines = {}
    for _, proofLine in ipairs(proof) do
        -- Content describing a line in a proof
        local content = {}

        -- Add line number to content; display line index if supplied
        local lineNumber = pandoc.Span(readStringAsMath(proofLine.index))
        lineNumber.classes = { "line-number" }
        content[#content + 1] = lineNumber

        -- Add indent markers to content
        for i = 1, proofLine.depth - 1 do
            local levelMarker = pandoc.Span ""
            if i == 1 then
                levelMarker.classes = { "first-level-marker" }
            else
                levelMarker.classes = { "level-marker" }
            end
            content[#content + 1] = levelMarker
        end

        -- Add final indent marker to content
        if proofLine.depth >= 1 then
            local formulaMarker = pandoc.Span ""
            if proofLine.hypothesis then
                formulaMarker.classes = { "hypothesis-marker" }
            else
                formulaMarker.classes = { "subproof-marker" }
            end
            table.insert(content, 1, formulaMarker)
        end

        -- Add formula to content
        local formula = pandoc.Span(readStringAsMath(proofLine.formula))
        formula.classes = { "proof-formula" }
        content[#content + 1] = formula

        -- Add justification to content
        if proofLine.justification then
            local justificationStr = proofLine.justification
            if proofLine.refs then
                justificationStr = justificationStr .. ": " .. "$" .. proofLine.refs .. "$"
            end
            local justification = pandoc.Span(readString(justificationStr))
            justification.classes = { "proof-justification" }
            content[#content + 1] = justification
        end

        -- Store line data as data-attributes for custom CSS formatting
        local line = pandoc.Div(content)
        line.classes = { "proof-line" }
        line.attributes["data-number"] = proofLine.line
        line.attributes["data-depth"] = proofLine.depth
        if proofLine.crossrefs then
            line.attributes["data-crossrefs"] = proofLine.crossrefs
        end
        if proofLine.ellipses == true then
            line.attributes["data-ellipses"] = "true"
        end
        lines[#lines + 1] = line -- list of .proof-line divs
    end
    local proofDiv = pandoc.Div(lines)
    proofDiv.classes = { "lproof" }
    return proofDiv
end

function Div(div)
    if div.classes[1] == "lproof" then
        local proof = parseProof(div.content[1].text)
        --quarto.log.output(proof)
        if lpeg.P("html"):match(FORMAT) then -- for HTML formatting
            return proofToHTML(proof)
        elseif lpeg.P("latex"):match(FORMAT) then
            return div -- for LaTeX formatting (TODO)
        end
    end
    return div
end

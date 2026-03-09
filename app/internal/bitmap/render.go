package bitmap

import (
	"fmt"
	"strings"
)

const (
	charSpacing = 0
	leftMargin  = 0
	fontHeight  = 7
	displayRows = 16
	pageWidth   = 32
)

var vOffsets = map[int]int{1: 9, 2: 1}

// ParseColor returns the RGB tuple for a color name or defaults to red.
func ParseColor(color string) [3]uint8 {
	if c, ok := Colors[color]; ok {
		return c
	}
	return Colors["red"]
}

// RenderTextToPages renders text into pages of 16 uint32 row values.
// scale=1 uses 5x7 font, scale=2 doubles each pixel.
func RenderTextToPages(text string, scale int) [][]uint32 {
	glyphs := make([]Glyph, 0, len(text))
	for _, ch := range text {
		if g, ok := Font[ch]; ok {
			glyphs = append(glyphs, g)
		} else {
			glyphs = append(glyphs, Font[' '])
		}
	}

	if len(glyphs) == 0 {
		return [][]uint32{make([]uint32, displayRows)}
	}

	scaled := charSpacing * scale
	var pages [][]uint32
	var current []Glyph
	currentWidth := leftMargin

	for _, g := range glyphs {
		gw := g.Width * scale
		needed := gw
		if len(current) > 0 {
			needed += scaled
		}
		if currentWidth+needed > pageWidth && len(current) > 0 {
			pages = append(pages, renderPage(current, scale))
			current = nil
			currentWidth = leftMargin
		}
		if len(current) > 0 {
			currentWidth += scaled
		}
		current = append(current, g)
		currentWidth += gw
	}
	if len(current) > 0 {
		pages = append(pages, renderPage(current, scale))
	}

	return pages
}

func renderPage(glyphs []Glyph, scale int) []uint32 {
	rows := make([]uint32, displayRows)
	vOffset := vOffsets[scale]
	if vOffset == 0 {
		vOffset = 4
	}
	scaled := charSpacing * scale
	col := leftMargin

	for _, g := range glyphs {
		for fontRow := 0; fontRow < fontHeight; fontRow++ {
			glyphVal := g.Rows[fontRow]
			for sy := 0; sy < scale; sy++ {
				dispRow := vOffset + fontRow*scale + sy
				if dispRow >= displayRows {
					break
				}
				for bit := 0; bit < g.Width; bit++ {
					if glyphVal&(1<<uint(g.Width-1-bit)) != 0 {
						for sx := 0; sx < scale; sx++ {
							pixCol := col + bit*scale + sx
							if pixCol < pageWidth {
								rows[dispRow] |= 1 << uint(pixCol)
							}
						}
					}
				}
			}
		}
		col += g.Width*scale + scaled
	}

	return rows
}

func renderLine(rows []uint32, text string, fontDict map[rune]Glyph, fHeight int, vOffset int) {
	col := leftMargin
	for _, ch := range strings.ToUpper(text) {
		g, ok := fontDict[ch]
		if !ok {
			g = fontDict[' ']
		}
		for fontRow := 0; fontRow < fHeight; fontRow++ {
			glyphVal := g.Rows[fontRow]
			dispRow := vOffset + fontRow
			if dispRow >= displayRows {
				break
			}
			for bit := 0; bit < g.Width; bit++ {
				if glyphVal&(1<<uint(g.Width-1-bit)) != 0 {
					pixCol := col + bit
					if pixCol < pageWidth {
						rows[dispRow] |= 1 << uint(pixCol)
					}
				}
			}
		}
		col += g.Width
		if col >= pageWidth-2 {
			break
		}
	}
}

// RenderFullscreen renders text centered on the display using FontBold at 2x scale.
func RenderFullscreen(text string) [][]uint32 {
	const scale = 2
	const boldFontHeight = 7

	// Collect glyphs and calculate total width
	glyphs := make([]Glyph, 0, len(text))
	totalWidth := 0
	for _, ch := range text {
		if g, ok := FontBold[ch]; ok {
			glyphs = append(glyphs, g)
			totalWidth += g.Width * scale
		} else if g, ok := FontBold[' ']; ok {
			glyphs = append(glyphs, g)
			totalWidth += g.Width * scale
		}
	}

	if len(glyphs) == 0 {
		return [][]uint32{make([]uint32, displayRows)}
	}

	// Center horizontally and vertically
	startCol := (pageWidth - totalWidth) / 2
	if startCol < 0 {
		startCol = 0
	}
	scaledHeight := boldFontHeight * scale
	startRow := (displayRows - scaledHeight) / 2

	rows := make([]uint32, displayRows)
	col := startCol

	for _, g := range glyphs {
		for fontRow := 0; fontRow < boldFontHeight; fontRow++ {
			glyphVal := g.Rows[fontRow]
			for sy := 0; sy < scale; sy++ {
				dispRow := startRow + fontRow*scale + sy
				if dispRow < 0 || dispRow >= displayRows {
					continue
				}
				for bit := 0; bit < g.Width; bit++ {
					if glyphVal&(1<<uint(g.Width-1-bit)) != 0 {
						for sx := 0; sx < scale; sx++ {
							pixCol := col + bit*scale + sx
							if pixCol >= 0 && pixCol < pageWidth {
								rows[dispRow] |= 1 << uint(pixCol)
							}
						}
					}
				}
			}
		}
		col += g.Width * scale
	}

	return [][]uint32{rows}
}

// RenderTwoLines renders two lines of text into a single page using the small
// or medium font. Line1 appears at top, line2 at bottom.
func RenderTwoLines(line1, line2 string, useMedium bool) [][]uint32 {
	rows := make([]uint32, displayRows)

	if useMedium {
		renderLine(rows, line1, FontMedium, 6, 1)
		renderLine(rows, line2, FontMedium, 6, 9)
	} else {
		renderLine(rows, line1, FontSmall, 5, 1)
		renderLine(rows, line2, FontSmall, 5, 9)
	}

	return [][]uint32{rows}
}

// PagesToASCII converts pages to an ASCII art string for preview.
func PagesToASCII(pages [][]uint32) string {
	var sb strings.Builder
	for pageIdx, page := range pages {
		sb.WriteString(fmt.Sprintf("Page %d (%d cols):\n", pageIdx, pageWidth))
		for rowIdx, rowVal := range page {
			var bits strings.Builder
			for col := 0; col < pageWidth; col++ {
				if (rowVal>>uint(col))&1 == 1 {
					bits.WriteByte('#')
				} else {
					bits.WriteByte('.')
				}
			}
			sb.WriteString(fmt.Sprintf("  Row %2d: %s  %08x\n", rowIdx, bits.String(), rowVal))
		}
		sb.WriteByte('\n')
	}
	return sb.String()
}

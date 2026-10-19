; vidtabs.inc -- screen line offset tables, included at the very start of
; the _TEXT of both assembly modules (lowlevel.asm at cs 6f26, tiles.asm at
; cs 7e5a: the two 1200-byte copies are byte-identical). Indexed by line*2.

CgaRowOfs	label	word		; CGA 320x200: even lines in bank 0, odd in bank 1
y		=	0
		rept	100
		dw	y*80, 2000h+y*80
y		=	y+1
		endm

EgaRowOfs	label	word		; EGA 320x200x16: 40 bytes per line
y		=	0
		rept	200
		dw	y*40
y		=	y+1
		endm

VgaRowOfs	label	word		; VGA 320x200x256: 320 bytes per line
y		=	0
		rept	200
		dw	y*320
y		=	y+1
		endm

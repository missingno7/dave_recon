; tiles.asm -- hand-written tile and sprite blitters, second assembly module.
;
; Placement (verified by tools/match_asm.py):
; @at 0x7e5a
; @seg _DATA 0x13aa
;   _TEXT  cs [0x7e5a, 0x9413)  = file [0x805a, 0x9613), word aligned; TLINK
;          pads one 00 byte before it (cs 0x7e59). CS.LIB follows at cs 0x9413.
;   _DATA  ds [0x13aa, 0x1439); the next module's data (palette at ds 143a,
;          levels at ds 173a) starts after one pad byte.
;
; Assembler: Turbo Assembler 2.0, single pass (see layout/assembler.json).
;
; Graphics come from the tile/sprite file loaded at TilesOff:TilesSeg: a
; dword count, then a dword offset per resource (resource n at +4+4n). Tiles
; (resources 0-52) are 16x16; sprites start with {width, height} words.
; Sprites are stored pre-shifted: EGA has 4 copies (x & 6), CGA 2 (x & 2),
; so the copy for x is resource n + (x & 6)/2 (EGA) or n + (x & 2)/2 (CGA).
;
; Three families of sprite routines exist for each adapter:
;   DrawMasked*  screen = (screen AND mask) OR sprite, clipped to the
;                playfield lines 13..165
;   SaveUnder* / RestoreUnder*  keep the background under a mask in a
;                caller buffer {x, y*2, width, height, size, mask copy, saved}
;   DrawXor* / DrawPic*  big pictures (any resource, 32-bit offsets on EGA),
;                horizontally clipped XOR or opaque copy
;
; Census ids (F_XXXX = FILE offset) are noted on every procedure.

		.MODEL	small
		LOCALS

; ---------------------------------------------------------------- equates

VT_CGA		equ	0		; values of the C global VideoType (byte)
VT_EGA		equ	1

CGA_SEG		equ	0B800h
EGA_SEG		equ	0A000h
TILECACHE_SEG	equ	0A800h		; EGA tiles cached in video memory (CacheEGATiles)

SC_INDEX	equ	3C4h		; EGA sequencer
SC_DATA		equ	3C5h
SC_MAPMASK	equ	2
GC_INDEX	equ	3CEh		; EGA graphics controller
GC_DATA		equ	3CFh
GC_READMAP	equ	4
GC_MODE		equ	5

PLAY_TOP	equ	13		; first and last+1 playfield line for masked sprites
PLAY_BOTTOM	equ	166
VIEW_COLS	equ	20		; tiles across the view
LEVEL_COLS	equ	100		; tiles across a level
NUM_TILES	equ	53

; ------------------------------------------------------- C-owned globals

		.DATA
		extrn	_D_4F86:byte	; video type: 0 CGA, 1 EGA, 2 VGA
		extrn	_D_56F0:word	; far pointer to the loaded tile file: offset
		extrn	_D_56F2:word	;  ... and segment
		extrn	_D_56F4:word	; current level
		extrn	_D_57A0:word	; horizontal scroll of the view, in tiles
		extrn	_D_173A:byte	; the levels: 10 x 1280 bytes, tiles at +256

VideoType	equ	_D_4F86
TilesOff	equ	_D_56F0
TilesSeg	equ	_D_56F2
CurLevel	equ	_D_56F4
ScrollX		equ	_D_57A0
Levels		equ	_D_173A

; ------------------------------------------------------ module variables

		public	_LevelPtr, _RowTimes100

		dw	0			; ds 13aa  (not referenced)
_LevelPtr	dd	0			; ds 13ac  far pointer to Levels (InitLevelPtr)
TileErrMsg	db	'Trouble loading tileset!$'	; ds 13b0  (not referenced)

LevelOfs	label	word			; ds 13c9  level n starts at Levels + n*1280
n		=	0
		rept	10
		dw	n*1280
n		=	n+1
		endm

_RowTimes100	label	word			; ds 13dd  row*100 (used by C)
n		=	0
		rept	10
		dw	n*LEVEL_COLS
n		=	n+1
		endm

TileRowOfs	label	word			; ds 13f1  view tile row -> CGA/EGA offset
n		=	1
		rept	10
		dw	n*640
n		=	n+1
		endm

VgaTileRowOfs	label	word			; ds 1405  view tile row -> VGA offset
n		=	1
		rept	10
		dw	n*16*320
n		=	n+1
		endm

BarPattern	db	8 dup (1Ah)		; ds 1419  one VGA border line, repeated
		db	18h,18h,18h,16h,16h,14h,12h,10h	;  10 times across
		db	10h,12h,14h,16h,16h,18h,18h,18h
		db	8 dup (1Ah)

		.CODE

; ---------------------- line offset tables: cs 7e5a CGA, 7fea EGA, 817a VGA

		include	vidtabs.inc

; void PrintDosString(char *s) -- file 850a: DOS print of a '$' string.
		public	_PrintDosString
_PrintDosString	proc	near
		push	bp
		mov	bp,sp
		mov	dx,[bp+4]
		mov	ah,9
		int	21h
		pop	bp
		ret
_PrintDosString	endp

; void InitLevelPtr(void) -- F_8516
		public	_InitLevelPtr
_InitLevelPtr	proc	near
		mov	ax,offset Levels
		mov	word ptr _LevelPtr,ax
		mov	ax,DGROUP
		mov	word ptr _LevelPtr+2,ax
		ret
_InitLevelPtr	endp

SprY		dw	0			; cs 8323

; ========================================================== EGA sprites

; void DrawMaskedEGA(int x, int y, int sprite, int mask) -- F_8525
		public	_DrawMaskedEGA
_DrawMaskedEGA	proc	near
		push	bp
		mov	bp,sp
		mov	ax,[bp+4]
		mov	bx,[bp+6]
		mov	cx,[bp+8]
		mov	dx,[bp+10]
		push	ds
		push	si
		push	di
		mov	si,cx
		mov	bp,dx
		mov	cs:SprY,bx
		cmp	bx,PLAY_BOTTOM
		jb	@@visible
		jmp	@@exit
@@visible:	shl	bx,1
		mov	di,cs:EgaRowOfs[bx]
		inc	bp			; offset table entries of the pre-shifted
		shl	bp,1			;  mask and sprite copies for this x
		shl	bp,1
		inc	si
		shl	si,1
		shl	si,1
		mov	cx,ax
		and	cx,6
		shl	cx,1
		add	si,cx
		add	bp,cx
		mov	bx,TilesSeg
		mov	ds,bx
		mov	si,[si]
		mov	bp,ds:[bp]
		shr	ax,1
		shr	ax,1
		shr	ax,1
		add	di,ax
		mov	bx,EGA_SEG
		mov	es,bx
		mov	bl,[si]			; bl = bytes per line
		add	bl,7
		shr	bl,1
		shr	bl,1
		shr	bl,1
		mov	bh,[si+2]		; bh = lines
		add	si,4
		add	bp,4
		cld
		mov	dx,SC_INDEX
		mov	al,SC_MAPMASK
		out	dx,al
		mov	dx,GC_INDEX
		mov	al,GC_READMAP
		out	dx,al
		mov	al,bh			; clip at the bottom of the playfield
		xor	ah,ah
		add	ax,cs:SprY
		cmp	ax,PLAY_BOTTOM
		jb	@@top
		mov	ax,PLAY_BOTTOM
		sub	ax,cs:SprY
		mov	bh,al
		jmp	@@line
@@top:		mov	ax,cs:SprY		; clip at the top of the playfield
		cmp	ax,PLAY_TOP
		ja	@@line
		mov	ax,PLAY_TOP
		sub	ax,cs:SprY
		sub	bh,al
		mov	dl,bl
		xor	dh,dh
		shl	dx,1
		shl	dx,1
@@skip:		add	si,dx
		add	bp,dx
		add	di,40
		dec	ax
		jne	@@skip
@@line:		mov	ah,8			; planes 3..0
		mov	ch,3
@@plane:	mov	al,ah
		mov	dx,SC_DATA
		out	dx,al
		mov	al,ch
		mov	dx,GC_DATA
		out	dx,al
		mov	dx,di
		mov	cl,bl
@@byte:		mov	al,es:[di]
		and	al,ds:[bp]
		or	al,[si]
		stosb
		inc	bp
		inc	si
		dec	cl
		jne	@@byte
		mov	di,dx
		dec	ch
		shr	ah,1
		test	ah,0Fh
		jne	@@plane
		add	di,40
		dec	bh
		jne	@@line
@@exit:		mov	al,0Fh
		mov	dx,SC_DATA
		out	dx,al
		mov	dx,GC_DATA
		xor	al,al
		out	dx,al
		pop	di
		pop	si
		pop	ds
		pop	bp
		ret
_DrawMaskedEGA	endp

MaskPtr		dw	0			; cs 8426  walks the mask copy in a save buffer
		dw	0			; cs 8428  (not referenced)

; void RestoreUnderEGA(int *buf) -- F_862A
		public	_RestoreUnderEGA
_RestoreUnderEGA proc	near
		push	bp
		mov	bp,sp
		mov	cx,[bp+4]
		push	si
		push	di
		mov	si,cx
		mov	ax,EGA_SEG
		mov	es,ax
		mov	ax,[si]			; x byte
		mov	bx,[si+2]		; y*2
		mov	di,cs:EgaRowOfs[bx]
		add	di,ax
		mov	bp,[si+4]		; bytes per line
		mov	bx,[si+6]		; lines
		mov	ax,[si+8]		; size of the mask copy
		add	si,10
		mov	cs:MaskPtr,si
		add	si,ax			; si -> saved background
		mov	dx,GC_INDEX		; write mode 0
		mov	al,GC_MODE
		out	dx,al
		inc	dx
		xor	al,al
		out	dx,al
@@line:		mov	ah,8
		mov	bh,3
@@plane:	mov	dx,SC_INDEX
		mov	al,SC_MAPMASK
		out	dx,al
		inc	dx
		mov	al,ah
		out	dx,al
		mov	dx,GC_INDEX
		mov	al,GC_READMAP
		out	dx,al
		inc	dx
		mov	al,bh
		out	dx,al
		mov	cx,bp
@@byte:		push	si
		mov	si,cs:MaskPtr
		mov	al,es:[di]
		and	al,[si]
		pop	si
		or	al,[si]
		stosb
		inc	si
		inc	cs:MaskPtr
		loop	@@byte
		sub	di,bp
		dec	bh
		shr	ah,1
		test	ah,0Fh
		jne	@@plane
		add	di,40
		dec	bl
		jne	@@line
		pop	di
		pop	si
		pop	bp
		ret
_RestoreUnderEGA endp

; void SaveUnderEGA(int x, int y, int mask, int *buf) -- F_86A9
		public	_SaveUnderEGA
_SaveUnderEGA	proc	near
		push	bp
		mov	bp,sp
		mov	ax,[bp+4]
		mov	bx,[bp+6]
		mov	cx,[bp+8]
		mov	dx,[bp+10]
		push	ds
		push	di
		push	si
		mov	si,cx
		mov	di,dx
		shl	bx,1
		push	ds
		pop	es
		mov	cx,TilesSeg
		mov	ds,cx
		inc	si
		shl	si,1
		shl	si,1
		mov	cx,ax
		and	cx,6
		shl	cx,1
		add	si,cx
		shr	ax,1
		shr	ax,1
		shr	ax,1
		mov	si,[si]
		mov	bp,[si]			; bytes per line
		add	bp,7
		shr	bp,1
		shr	bp,1
		shr	bp,1
		mov	dx,[si+2]		; lines
		add	si,4
		mov	es:[di],ax		; buffer header
		mov	es:[di+2],bx
		mov	es:[di+4],bp
		mov	es:[di+6],dx
		add	di,8
		xchg	dx,ax
		push	bx
		push	ax
		mov	bl,al
		mov	ax,bp
		shl	ax,1
		shl	ax,1
		mul	bl
		mov	es:[di],ax		; size of the mask copy (4 planes)
		add	di,2
		mov	cx,ax
		cld
		mov	cs:MaskPtr,di
		rep	movsb			; copy the mask
		pop	ax
		pop	bx
		mov	si,EGA_SEG
		mov	ds,si
		mov	si,cs:EgaRowOfs[bx]
		add	si,dx
		mov	bl,al
		mov	dx,GC_INDEX
		mov	al,GC_MODE
		out	dx,al
		inc	dx
		xor	al,al
		out	dx,al
@@line:		mov	ah,3
@@plane:	mov	dx,GC_INDEX
		mov	al,GC_READMAP
		out	dx,al
		inc	dx
		mov	al,ah
		out	dx,al
		mov	cx,bp
@@byte:		mov	al,[si]			; save screen AND NOT mask
		push	si
		mov	si,cs:MaskPtr
		mov	bh,es:[si]
		xor	bh,0FFh
		pop	si
		and	al,bh
		stosb
		inc	cs:MaskPtr
		inc	si
		loop	@@byte
		sub	si,bp
		dec	ah
		jns	@@plane
		add	si,40
		dec	bl
		jne	@@line
		mov	al,3
		out	dx,al
		pop	si
		pop	di
		pop	ds
		pop	bp
		ret
_SaveUnderEGA	endp

SprX		dw	0			; cs 8576

; ========================================================== VGA sprites

; void DrawMaskedVGA(int x, int y, int sprite, int mask) -- F_8778
		public	_DrawMaskedVGA
_DrawMaskedVGA	proc	near
		push	bp
		mov	bp,sp
		mov	ax,[bp+4]
		mov	bx,[bp+6]
		mov	cx,[bp+8]
		mov	dx,[bp+10]
		push	ds
		push	si
		push	di
		mov	si,cx
		mov	di,dx
		xor	bh,bh
		shl	bx,1
		mov	cx,TilesSeg
		mov	ds,cx
		inc	si
		shl	si,1
		shl	si,1
		inc	di
		shl	di,1
		shl	di,1
		mov	si,[si]
		mov	bp,[di]
		mov	dh,[si]			; width
		mov	dl,[si+2]		; lines
		mov	cx,ax
		add	si,4
		add	bp,4
		mov	ax,EGA_SEG
		mov	es,ax
		mov	di,cs:VgaRowOfs[bx]
		mov	cs:SprX,cx
		add	di,cx
		xor	ch,ch
		mov	cl,dh
		xor	dh,dh
		shr	bx,1
		mov	ax,bx
		cmp	ax,PLAY_TOP
		ja	@@below
		add	ax,dx			; starts above the playfield
		cmp	ax,PLAY_TOP
		jb	@@exit
		push	cx
		sub	ax,PLAY_TOP
		mov	dx,ax
		mov	ax,PLAY_TOP
		sub	ax,bx
		mul	cl
		add	si,ax
		add	bp,ax
		mov	bx,PLAY_TOP*2
		mov	di,cs:VgaRowOfs[bx]
		add	di,cs:SprX
		pop	cx
		jmp	short @@draw
@@below:	cmp	ax,PLAY_BOTTOM
		jae	@@exit
		add	ax,dx
		cmp	ax,PLAY_BOTTOM
		jb	@@draw
		mov	dx,PLAY_BOTTOM
		sub	dx,bx
@@draw:		mov	ah,cl
@@byte:		mov	al,es:[di]
		and	al,ds:[bp]
		or	al,[si]
		stosb
		inc	si
		inc	bp
		loop	@@byte
		mov	cl,ah
		sub	di,cx
		add	di,320
		dec	dx
		jne	@@byte
@@exit:		pop	di
		pop	si
		pop	ds
		pop	bp
		ret
_DrawMaskedVGA	endp

; void RestoreUnderVGA(int *buf) -- F_882C
		public	_RestoreUnderVGA
_RestoreUnderVGA proc	near
		push	bp
		mov	bp,sp
		mov	cx,[bp+4]
		push	si
		push	di
		mov	si,cx
		mov	ax,EGA_SEG
		mov	es,ax
		mov	ax,[si]
		mov	bx,[si+2]
		mov	bp,[si+4]
		mov	dx,[si+6]
		add	si,10
		mov	di,cs:VgaRowOfs[bx]
		add	di,ax
		mov	bx,si			; bx -> mask copy
		add	si,[si-2]		; si -> saved background
@@line:		mov	cx,bp
@@byte:		mov	al,es:[di]
		and	al,[bx]
		or	al,[si]
		stosb
		inc	si
		inc	bx
		loop	@@byte
		sub	di,bp
		add	di,320
		dec	dl
		jne	@@line
		pop	di
		pop	si
		pop	bp
		ret
_RestoreUnderVGA endp

; void SaveUnderVGA(int x, int y, int mask, int *buf) -- F_8871
		public	_SaveUnderVGA
_SaveUnderVGA	proc	near
		push	bp
		mov	bp,sp
		mov	ax,[bp+4]
		mov	bx,[bp+6]
		mov	cx,[bp+8]
		mov	dx,[bp+10]
		push	ds
		push	di
		push	si
		mov	si,cx
		mov	di,dx
		shl	bx,1
		push	ds
		pop	es
		mov	cx,TilesSeg
		mov	ds,cx
		inc	si
		shl	si,1
		shl	si,1
		mov	si,[si]
		mov	bp,[si]
		mov	dx,[si+2]
		add	si,4
		mov	es:[di],ax
		mov	es:[di+2],bx
		mov	es:[di+4],bp
		mov	es:[di+6],dx
		add	di,8
		xchg	dx,ax
		push	bx
		push	ax
		mov	bl,al
		mov	ax,bp
		mul	bl
		mov	es:[di],ax
		add	di,2
		mov	cx,ax
		cld
		mov	cs:MaskPtr,di
		rep	movsb
		pop	ax
		pop	bx
		mov	si,EGA_SEG
		mov	ds,si
		mov	si,cs:VgaRowOfs[bx]
		add	si,dx
		mov	bx,cs:MaskPtr
		mov	dl,al
@@line:		mov	cx,bp
@@byte:		mov	al,es:[bx]
		xor	al,0FFh
		and	al,[si]
		stosb
		inc	si
		inc	bx
		loop	@@byte
		sub	si,bp
		add	si,320
		dec	dl
		jne	@@line
		pop	si
		pop	di
		pop	ds
		pop	bp
		ret
_SaveUnderVGA	endp

; ========================================================== CGA sprites

; void DrawMaskedCGA(int x, int y, int sprite, int mask) -- F_88FD
		public	_DrawMaskedCGA
_DrawMaskedCGA	proc	near
		push	bp
		mov	bp,sp
		mov	ax,[bp+4]
		mov	bx,[bp+6]
		mov	cx,[bp+8]
		mov	dx,[bp+10]
		push	ds
		push	si
		push	di
		mov	si,cx
		mov	di,dx
		xor	bh,bh
		shl	bx,1
		mov	cx,TilesSeg
		mov	ds,cx
		inc	si
		shl	si,1
		shl	si,1
		inc	di
		shl	di,1
		shl	di,1
		mov	dx,ax
		and	dx,2
		shl	dx,1
		add	si,dx
		add	di,dx
		mov	si,[si]
		mov	di,[di]
		mov	bp,di
		mov	dx,[si]			; dh = bytes per line
		add	dx,3
		shr	dx,1
		shr	dx,1
		mov	dh,dl
		mov	dl,[si+2]		; dl = lines
		shr	ax,1
		shr	ax,1
		mov	cx,ax
		add	si,4
		add	bp,4
		mov	ax,CGA_SEG
		mov	es,ax
@@line:		cmp	bx,PLAY_BOTTOM*2
		jae	@@exit
		cmp	bx,PLAY_TOP*2
		ja	@@visible
		mov	al,dh			; above the playfield: skip the line
		xor	ah,ah
		add	si,ax
		add	bp,ax
		jmp	short @@next
@@visible:	mov	di,cs:CgaRowOfs[bx]
		add	di,cx
		mov	ah,dh
@@byte:		mov	al,es:[di]
		and	al,ds:[bp]
		or	al,[si]
		mov	es:[di],al
		inc	si
		inc	bp
		inc	di
		dec	ah
		jne	@@byte
@@next:		add	bx,2
		dec	dl
		jne	@@line
@@exit:		pop	di
		pop	si
		pop	ds
		pop	bp
		ret
_DrawMaskedCGA	endp

; void RestoreUnderCGA(int *buf) -- F_8994
		public	_RestoreUnderCGA
_RestoreUnderCGA proc	near
		push	bp
		mov	bp,sp
		mov	cx,[bp+4]
		push	si
		push	di
		mov	si,cx
		mov	ax,CGA_SEG
		mov	es,ax
		mov	dx,[si]
		mov	bx,[si+2]
		mov	bp,[si+4]
		mov	ax,[si+6]
		mov	ah,al
		add	si,10
		mov	cs:MaskPtr,si
		add	si,[si-2]
@@line:		mov	di,cs:CgaRowOfs[bx]
		add	di,dx
		mov	cx,bp
@@byte:		push	si
		mov	si,cs:MaskPtr
		mov	al,[si]
		pop	si
		and	al,es:[di]
		or	al,[si]
		stosb
		inc	si
		inc	cs:MaskPtr
		loop	@@byte
		add	bx,2
		dec	ah
		jne	@@line
		pop	di
		pop	si
		pop	bp
		ret
_RestoreUnderCGA endp

; void SaveUnderCGA(int x, int y, int mask, int *buf) -- F_89E6
		public	_SaveUnderCGA
_SaveUnderCGA	proc	near
		push	bp
		mov	bp,sp
		mov	ax,[bp+4]
		mov	bx,[bp+6]
		mov	cx,[bp+8]
		mov	dx,[bp+10]
		push	ds
		push	di
		push	si
		mov	si,cx
		mov	di,dx
		shl	bx,1
		push	ds
		pop	es
		mov	cx,TilesSeg
		mov	ds,cx
		inc	si
		shl	si,1
		shl	si,1
		mov	dx,ax
		and	dx,2
		shl	dx,1
		add	si,dx
		shr	ax,1
		shr	ax,1
		mov	si,[si]
		mov	bp,[si]
		add	bp,3
		shr	bp,1
		shr	bp,1
		mov	dx,[si+2]
		add	si,4
		mov	es:[di],ax
		mov	es:[di+2],bx
		mov	es:[di+4],bp
		mov	es:[di+6],dx
		add	di,8
		xchg	dx,ax
		mov	ah,al
		push	ax
		push	bx
		mov	bl,ah
		mov	ax,bp
		mul	bl
		mov	es:[di],ax
		add	di,2
		mov	cs:MaskPtr,di
		mov	cx,ax
		rep	movsb
		pop	bx
		pop	ax
		mov	si,CGA_SEG
		mov	ds,si
@@line:		mov	si,cs:CgaRowOfs[bx]
		add	si,dx
		mov	cx,bp
@@byte:		push	si
		mov	si,cs:MaskPtr
		mov	al,es:[si]
		pop	si
		xor	al,0FFh
		and	al,[si]
		stosb
		inc	si
		inc	cs:MaskPtr
		loop	@@byte
		add	bx,2
		dec	ah
		jne	@@line
		pop	si
		pop	di
		pop	ds
		pop	bp
		ret
_SaveUnderCGA	endp

; ============================================= pictures (big resources)

; locate resource si-th entry's data on EGA: 32-bit offset -> DS:SI
; (bank = high word * 1000h paragraphs, then the low word normalized)
EgaFarResource	macro
		push	bx
		mov	ax,TilesSeg
		mov	bx,ax
		mov	ds,ax
		xor	al,al
		mov	ah,[si+2]
		shl	ah,1
		shl	ah,1
		shl	ah,1
		shl	ah,1
		add	ax,bx
		mov	si,[si]
		mov	ds,ax
		mov	ax,si
		shr	ax,1
		shr	ax,1
		shr	ax,1
		shr	ax,1
		mov	bx,ds
		add	bx,ax
		mov	ds,bx
		and	si,0Fh
		pop	bx
		endm

; DS:SI += SI paragraphs (normalize a near offset into the segment)
NormalizeDSSI	macro
		push	bx
		push	ax
		mov	ax,si
		shr	ax,1
		shr	ax,1
		shr	ax,1
		shr	ax,1
		mov	bx,ds
		add	bx,ax
		mov	ds,bx
		and	si,0Fh
		pop	ax
		pop	bx
		endm

; void DrawXorEGA(int x, int y, int pic) -- F_8A88
		public	_DrawXorEGA
_DrawXorEGA	proc	near
		push	bp
		mov	bp,sp
		mov	ax,[bp+4]
		mov	bx,[bp+6]
		mov	cx,[bp+8]
		push	ds
		push	si
		push	di
		mov	si,cx
		shl	bx,1
		mov	di,cs:EgaRowOfs[bx]
		inc	si
		shl	si,1
		shl	si,1
		mov	cx,ax
		and	cx,6
		shl	cx,1
		add	si,cx
		shr	ax,1
		shr	ax,1
		shr	ax,1
		cmp	ah,1Fh			; x was negative
		jne	@@xok
		mov	ah,0FFh
@@xok:		mov	cs:ClipX,ax
		mov	ax,EGA_SEG
		mov	es,ax
		EgaFarResource
		mov	bp,[si]
		add	bp,7
		shr	bp,1
		shr	bp,1
		shr	bp,1
		mov	bx,[si+2]
		add	si,4
		cld
		mov	cs:ClipLeft,0
		mov	cs:ClipRight,0
		mov	ax,cs:ClipX
		mov	cx,ax
		cmp	cx,40
		jae	@@offleft
		add	cx,bp
		cmp	cx,40
		jb	@@draw
		sub	cx,40			; runs off the right edge
		mov	cs:ClipRight,cx
		mov	bp,40
		sub	bp,ax
		jmp	short @@draw
@@offleft:	add	cx,bp			; starts left of the screen
		cmp	cx,40
		jae	@@exit
		neg	ax
		mov	cs:ClipLeft,ax
		sub	bp,ax
		je	@@exit
		xor	ax,ax
@@draw:		add	di,ax
		mov	dx,SC_INDEX
		mov	al,SC_MAPMASK
		out	dx,al
		mov	dx,GC_INDEX
		mov	al,GC_READMAP
		out	dx,al
@@line:		mov	ah,8
		mov	bh,3
@@plane:	mov	al,ah
		mov	dx,SC_DATA
		out	dx,al
		mov	dx,GC_DATA
		mov	al,bh
		out	dx,al
		mov	dx,di
		mov	cx,bp
		add	si,cs:ClipLeft
@@byte:		mov	al,es:[di]
		xor	al,[si]
		stosb
		inc	si
		loop	@@byte
		add	si,cs:ClipRight
		mov	di,dx
		dec	bh
		shr	ah,1
		test	ah,0Fh
		jne	@@plane
		add	di,40
		dec	bl
		jne	@@line
		mov	al,0Fh
		mov	dx,SC_DATA
		out	dx,al
		mov	dx,GC_DATA
		xor	al,al
		out	dx,al
@@exit:		pop	di
		pop	si
		pop	ds
		pop	bp
		ret
_DrawXorEGA	endp

; void DrawPicEGA(int x, int y, int pic) -- F_8B9F: opaque, unclipped
		public	_DrawPicEGA
_DrawPicEGA	proc	near
		push	bp
		mov	bp,sp
		mov	ax,[bp+4]
		mov	bx,[bp+6]
		mov	cx,[bp+8]
		push	ds
		push	si
		push	di
		mov	si,cx
		shl	bx,1
		mov	di,cs:EgaRowOfs[bx]
		inc	si
		shl	si,1
		shl	si,1
		mov	cx,ax
		and	cx,6
		shl	cx,1
		add	si,cx
		shr	ax,1
		shr	ax,1
		shr	ax,1
		cmp	ah,1Fh
		jne	@@xok
		mov	ah,0FFh
@@xok:		mov	cs:ClipX,ax
		mov	ax,EGA_SEG
		mov	es,ax
		EgaFarResource
		mov	bp,[si]
		add	bp,7
		shr	bp,1
		shr	bp,1
		shr	bp,1
		mov	bx,[si+2]
		add	si,4
		cld
		add	di,cs:ClipX
		mov	dx,SC_INDEX
		mov	al,SC_MAPMASK
		out	dx,al
		mov	dx,GC_INDEX
		mov	al,GC_READMAP
		out	dx,al
@@line:		mov	ah,8
		mov	bh,3
@@plane:	mov	al,ah
		mov	dx,SC_DATA
		out	dx,al
		mov	dx,GC_DATA
		mov	al,bh
		out	dx,al
		mov	dx,di
		mov	cx,bp
		rep	movsb
		mov	di,dx
		dec	bh
		shr	ah,1
		test	ah,0Fh
		jne	@@plane
		add	di,40
		dec	bl
		jne	@@line
		mov	al,0Fh
		mov	dx,SC_DATA
		out	dx,al
		mov	dx,GC_DATA
		xor	al,al
		out	dx,al
		pop	di
		pop	si
		pop	ds
		pop	bp
		ret
_DrawPicEGA	endp

; void DrawXorVGA(int x, int y, int pic) -- F_8C66
		public	_DrawXorVGA
_DrawXorVGA	proc	near
		push	bp
		mov	bp,sp
		mov	ax,[bp+4]
		mov	bx,[bp+6]
		mov	cx,[bp+8]
		push	ds
		push	si
		push	di
		mov	si,cx
		shl	bx,1
		mov	dx,ax
		mov	ax,EGA_SEG
		mov	es,ax
		inc	si
		shl	si,1
		shl	si,1
		mov	di,TilesSeg
		mov	ds,di
		mov	si,[si]
		NormalizeDSSI
		mov	bp,[si]
		cld
		mov	cs:ClipLeft,0
		mov	cs:ClipRight,0
		mov	ax,dx
		cmp	ax,320
		jae	@@offleft
		add	ax,bp
		cmp	ax,320
		jb	@@draw
		sub	ax,320
		mov	cs:ClipRight,ax
		mov	bp,320
		sub	bp,dx
		jmp	short @@draw
@@offleft:	add	ax,bp
		cmp	ax,320
		jae	@@exit
		neg	dx
		mov	cs:ClipLeft,dx
		sub	bp,dx
		je	@@exit
		xor	dx,dx
@@draw:		mov	ah,[si+2]
		add	si,4
		cmp	bx,200*2
		jae	@@exit
@@line:		mov	di,cs:VgaRowOfs[bx]
		add	di,dx
		mov	cx,bp
		add	si,cs:ClipLeft
@@byte:		lodsb
		xor	es:[di],al
		inc	di
		loop	@@byte
		add	si,cs:ClipRight
		add	bx,2
		dec	ah
		jne	@@line
@@exit:		pop	di
		pop	si
		pop	ds
		pop	bp
		ret
_DrawXorVGA	endp

; void DrawPicVGA(int x, int y, int pic) -- F_8D17
		public	_DrawPicVGA
_DrawPicVGA	proc	near
		push	bp
		mov	bp,sp
		mov	ax,[bp+4]
		mov	bx,[bp+6]
		mov	cx,[bp+8]
		push	ds
		push	si
		push	di
		mov	si,cx
		shl	bx,1
		mov	dx,ax
		mov	ax,EGA_SEG
		mov	es,ax
		inc	si
		shl	si,1
		shl	si,1
		mov	di,TilesSeg
		mov	ds,di
		xor	al,al			; bank of the 32-bit offset
		mov	ah,[si+2]
		shl	ah,1
		shl	ah,1
		shl	ah,1
		shl	ah,1
		add	di,ax
		mov	si,[si]
		mov	ds,di
		NormalizeDSSI
		mov	bp,[si]
		cld
		mov	ah,[si+2]
		add	si,4
		cmp	bx,200*2
		jae	@@exit
		mov	di,cs:VgaRowOfs[bx]
		add	di,dx
@@line:		mov	cx,bp
		rep	movsb
		sub	di,bp
		add	di,320
		dec	ah
		jne	@@line
@@exit:		pop	di
		pop	si
		pop	ds
		pop	bp
		ret
_DrawPicVGA	endp

ClipX		dw	0			; cs 8b8f  first byte column (may be negative)
ClipLeft	dw	0			; cs 8b91  bytes skipped per line on the left
ClipRight	dw	0			; cs 8b93  ... and on the right

; void DrawXorCGA(int x, int y, int pic) -- F_8D95
		public	_DrawXorCGA
_DrawXorCGA	proc	near
		push	bp
		mov	bp,sp
		mov	ax,[bp+4]
		mov	bx,[bp+6]
		mov	cx,[bp+8]
		push	ds
		push	si
		push	di
		mov	si,cx
		inc	si
		test	ax,2			; odd 2-pixel position: shifted copy
		je	@@even
		inc	si
@@even:		shr	ax,1
		shr	ax,1
		cmp	ah,3Fh			; x was negative
		jne	@@xok
		mov	ah,0FFh
@@xok:		shl	bx,1
		mov	dx,ax
		mov	ax,CGA_SEG
		mov	es,ax
		shl	si,1
		shl	si,1
		mov	di,TilesSeg
		mov	ds,di
		mov	si,[si]
		NormalizeDSSI
		mov	bp,[si]
		add	bp,3
		shr	bp,1
		shr	bp,1
		cld
		mov	cs:ClipLeft,0
		mov	cs:ClipRight,0
		mov	ax,dx
		cmp	ax,80
		jae	@@offleft
		add	ax,bp
		cmp	ax,80
		jb	@@draw
		sub	ax,80
		mov	cs:ClipRight,ax
		mov	bp,80
		sub	bp,dx
		jmp	short @@draw
@@offleft:	add	ax,bp
		cmp	ax,80
		jae	@@exit
		neg	dx
		mov	cs:ClipLeft,dx
		sub	bp,dx
		je	@@exit
		xor	dx,dx
@@draw:		mov	ah,[si+2]
		add	si,4
		cmp	bx,200*2
		jae	@@exit
@@line:		mov	di,cs:CgaRowOfs[bx]
		add	di,dx
		mov	cx,bp
		add	si,cs:ClipLeft
@@byte:		lodsb
		xor	es:[di],al
		inc	di
		loop	@@byte
		add	si,cs:ClipRight
		add	bx,2
		dec	ah
		jne	@@line
@@exit:		pop	di
		pop	si
		pop	ds
		pop	bp
		ret
_DrawXorCGA	endp

; void DrawPicCGA(int x, int y, int pic) -- F_8E5E
		public	_DrawPicCGA
_DrawPicCGA	proc	near
		push	bp
		mov	bp,sp
		mov	ax,[bp+4]
		mov	bx,[bp+6]
		mov	cx,[bp+8]
		push	ds
		push	si
		push	di
		mov	si,cx
		inc	si
		test	ax,2
		je	@@even
		inc	si
@@even:		shr	ax,1
		shr	ax,1
		cmp	ah,3Fh
		jne	@@xok
		mov	ah,0FFh
@@xok:		shl	bx,1
		mov	dx,ax
		mov	ax,CGA_SEG
		mov	es,ax
		shl	si,1
		shl	si,1
		mov	di,TilesSeg
		mov	ds,di
		mov	si,[si]
		NormalizeDSSI
		mov	bp,[si]
		add	bp,3
		shr	bp,1
		shr	bp,1
		cld
		mov	ah,[si+2]
		add	si,4
		cmp	bx,200*2
		jae	@@exit
@@line:		mov	di,cs:CgaRowOfs[bx]
		add	di,dx
		mov	cx,bp
		rep	movsb
		add	bx,2
		dec	ah
		jne	@@line
@@exit:		pop	di
		pop	si
		pop	ds
		pop	bp
		ret
_DrawPicCGA	endp

; ================================================================ tiles

; fetch the next level byte (tile number) and point DS:SI at the tile's
; first word in the tile file (CGA: 64 bytes, VGA: 256 bytes per tile)
TileFetch	macro
		lodsb
		mov	dx,si
		mov	si,TilesOff
		mov	bp,TilesSeg
		mov	ds,bp
		mov	si,[si+4]
		endm

; one 16-pixel CGA line pair: even line, then odd line
CgaTileLines	macro	back
		movsw
		movsw
		add	di,bx			; bx = 2000h-4: down to the odd bank
		movsw
		movsw
		sub	di,back
		endm

; one 16-pixel EGA line through the latches
EgaTileLine	macro
		movsb
		movsb
		add	di,bx			; bx = 40-2
		endm

VgaTileLine	macro
		rept	8
		movsw
		endm
		endm

; void DrawLevelView(void) -- F_8EDA: the 20x9.5-tile playfield from the
; current level at the current scroll position, starting at line 16.
		public	_DrawLevelView
_DrawLevelView	proc	near
		push	bp
		push	si
		push	di
		mov	bx,CurLevel
		shl	bx,1
		mov	si,offset Levels+256
		add	si,LevelOfs[bx]
		add	si,ScrollX
		cmp	VideoType,VT_CGA
		je	@@cga
		cmp	VideoType,VT_EGA
		jne	@@notega
		jmp	@@ega
@@notega:	jmp	@@vga

@@cga:		mov	ax,CGA_SEG
		mov	es,ax
		cld
		mov	bx,2000h-4
		mov	di,16/2*80
		mov	cx,9*256+VIEW_COLS	; ch = full tile rows, cl = columns
@@cgatile:	TileFetch
		xor	ah,ah
		shl	ax,1			; * 64
		shl	ax,1
		shl	ax,1
		shl	ax,1
		shl	ax,1
		shl	ax,1
		add	si,ax
		rept	7
		CgaTileLines	2000h-80+4
		endm
		CgaTileLines	2000h+7*80	; back up to the next tile
		mov	si,dx
		mov	ax,DGROUP
		mov	ds,ax
		dec	cl
		jne	@@cgatile
		add	si,LEVEL_COLS-VIEW_COLS
		add	di,7*80
		mov	cl,VIEW_COLS
		dec	ch
		je	@@cgalast
		jmp	@@cgatile
@@cgalast:	mov	cl,VIEW_COLS		; bottom row: top 6 lines only
@@cgahalf:	TileFetch
		xor	ah,ah
		shl	ax,1
		shl	ax,1
		shl	ax,1
		shl	ax,1
		shl	ax,1
		shl	ax,1
		add	si,ax
		rept	2
		CgaTileLines	2000h-80+4
		endm
		CgaTileLines	2000h+2*80
		mov	si,dx
		mov	ax,DGROUP
		mov	ds,ax
		dec	cl
		jne	@@cgahalf
		pop	di
		pop	si
		pop	bp
		ret

@@ega:		mov	dx,SC_INDEX		; all planes, write mode 1 (latch copy
		mov	al,SC_MAPMASK		;  from the tile cache)
		out	dx,al
		inc	dx
		mov	al,0Fh
		out	dx,al
		mov	dx,GC_INDEX
		mov	ax,0100h+GC_MODE
		out	dx,ax
		mov	ax,EGA_SEG
		mov	es,ax
		cld
		mov	di,16*40
		mov	bx,40-2
		mov	cx,9*256+VIEW_COLS
@@egatile:	lodsb
		mov	dx,si
		mov	bp,TILECACHE_SEG
		mov	ds,bp
		xor	ah,ah
		shl	ax,1			; * 32
		shl	ax,1
		shl	ax,1
		shl	ax,1
		shl	ax,1
		mov	si,ax
		rept	15
		EgaTileLine
		endm
		movsb
		movsb
		sub	di,15*40
		mov	si,dx
		mov	ax,DGROUP
		mov	ds,ax
		dec	cl
		jne	@@egatile
		add	si,LEVEL_COLS-VIEW_COLS
		add	di,15*40
		mov	cl,VIEW_COLS
		dec	ch
		je	@@egalast
		jmp	@@egatile
@@egalast:	mov	cl,VIEW_COLS
@@egahalf:	lodsb
		mov	dx,si
		mov	bp,TILECACHE_SEG
		mov	ds,bp
		xor	ah,ah
		shl	ax,1
		shl	ax,1
		shl	ax,1
		shl	ax,1
		shl	ax,1
		mov	si,ax
		rept	5
		EgaTileLine
		endm
		movsb
		movsb
		sub	di,5*40
		mov	si,dx
		mov	ax,DGROUP
		mov	ds,ax
		dec	cl
		jne	@@egahalf
		mov	dx,GC_INDEX		; back to write mode 0
		mov	ax,GC_MODE
		out	dx,ax
		pop	di
		pop	si
		pop	bp
		ret

@@vga:		mov	ax,EGA_SEG
		mov	es,ax
		cld
		mov	di,16*320
		mov	bx,320-16
		mov	cx,9*256+VIEW_COLS
@@vgatile:	TileFetch
		mov	ah,al			; * 256
		xor	al,al
		add	si,ax
		rept	15
		VgaTileLine
		add	di,bx
		endm
		VgaTileLine
		sub	di,15*320
		mov	si,dx
		mov	ax,DGROUP
		mov	ds,ax
		dec	cl
		je	@@vgarow
		jmp	@@vgatile
@@vgarow:	add	si,LEVEL_COLS-VIEW_COLS
		add	di,15*320
		mov	cl,VIEW_COLS
		dec	ch
		je	@@vgalast
		jmp	@@vgatile
@@vgalast:	mov	cl,VIEW_COLS
@@vgahalf:	TileFetch
		mov	ah,al
		xor	al,al
		add	si,ax
		rept	5
		VgaTileLine
		add	di,bx
		endm
		VgaTileLine
		sub	di,5*320
		mov	si,dx
		mov	ax,DGROUP
		mov	ds,ax
		dec	cl
		je	@@done
		jmp	@@vgahalf
@@done:		pop	di
		pop	si
		pop	bp
		ret
_DrawLevelView	endp

; void DrawViewBorders(void) -- F_9211: the lines above (12-13) and below
; (167-168) the playfield.
		public	_DrawViewBorders
_DrawViewBorders proc	near
		cmp	VideoType,VT_CGA
		je	@@cga
		cmp	VideoType,VT_EGA
		je	@@ega
		jmp	@@vga
@@cga:		mov	ax,CGA_SEG
		mov	es,ax
		mov	cx,40
		xor	bx,bx
@@cgaword:	mov	word ptr es:[bx+12/2*80],0FFFFh
		mov	word ptr es:[bx+2000h+13/2*80],0FFFFh
		mov	word ptr es:[bx+2000h+167/2*80],0FFFFh
		mov	word ptr es:[bx+168/2*80],0FFFFh
		add	bx,2
		loop	@@cgaword
		ret
@@ega:		mov	ax,EGA_SEG
		mov	es,ax
		mov	dx,SC_INDEX
		mov	al,SC_MAPMASK
		out	dx,al
		inc	dx
		mov	al,7			; planes 0-2
		out	dx,al
		mov	al,0FFh
		xor	bx,bx
		mov	cx,40
@@egabyte:	mov	es:[bx+12*40],al
		mov	es:[bx+13*40],al
		mov	es:[bx+167*40],al
		mov	es:[bx+168*40],al
		inc	bx
		loop	@@egabyte
		mov	dx,SC_INDEX
		mov	al,SC_MAPMASK
		out	dx,al
		inc	dx
		mov	al,8			; plane 3
		out	dx,al
		xor	al,al
		mov	bx,39
		mov	cx,40
@@egaplane3:	mov	es:[bx+6*40],al
		mov	es:[bx+7*40],al
		mov	es:[bx+83*40],al
		mov	es:[bx+84*40],al
		inc	bx
		loop	@@egaplane3
		mov	dx,SC_INDEX
		mov	al,SC_MAPMASK
		out	dx,al
		inc	dx
		mov	al,0Fh
		out	dx,al
		ret
@@vga:		mov	ax,EGA_SEG
		mov	es,ax
		mov	di,12*320
		call	VgaBarLine
		call	VgaBarLine
		mov	di,167*320
		call	VgaBarLine
		call	VgaBarLine
		ret
_DrawViewBorders endp

VgaBarLine	proc	near			; F_92C7: one 320-pixel line at ES:DI
		mov	bx,10
@@part:		mov	si,offset BarPattern
		mov	cx,32
		rep	movsb
		dec	bx
		jne	@@part
		ret
VgaBarLine	endp

; void DrawTile(int x, int y, int tile) -- F_92D6: tile at view cell (x, y)
		public	_DrawTile
_DrawTile	proc	near
		push	bp
		mov	bp,sp
		mov	bx,[bp+6]
		mov	ax,[bp+4]
		mov	cx,[bp+8]
		mov	ah,bl
		call	DrawTileAt
		pop	bp
		ret
_DrawTile	endp

; DrawTileAt -- F_92E9: AL = column, AH = row (9 = the half row), CL = tile
DrawTileAt	proc	near
		push	dx
		push	bx
		push	bp
		push	di
		push	si
		cmp	VideoType,VT_CGA
		je	@@cga
		cmp	VideoType,VT_EGA
		je	@@isega
		jmp	@@vga
@@isega:	jmp	@@ega

@@cga:		mov	bl,ah
		xor	bh,bh
		shl	bx,1
		mov	di,TileRowOfs[bx]
		xor	ah,ah
		shl	ax,1
		shl	ax,1
		add	di,ax
		mov	ax,CGA_SEG
		mov	es,ax
		cld
		cmp	bx,9*2
		je	@@cgahalf
		mov	bx,2000h-4
		mov	bp,TilesSeg
		mov	ds,bp
		add	si,TilesOff
		mov	si,ds:[4]
		xor	ch,ch
		shl	cx,1
		shl	cx,1
		shl	cx,1
		shl	cx,1
		shl	cx,1
		shl	cx,1
		add	si,cx
		rept	7
		CgaTileLines	2000h-80+4
		endm
		movsw
		movsw
		add	di,bx
		movsw
		movsw
@@exit:		mov	ax,DGROUP
		mov	ds,ax
		pop	si
		pop	di
		pop	bp
		pop	bx
		pop	dx
		ret
@@cgahalf:	mov	bx,2000h-4
		mov	bp,TilesSeg
		mov	ds,bp
		add	si,TilesOff
		mov	si,ds:[4]
		xor	ch,ch
		shl	cx,1
		shl	cx,1
		shl	cx,1
		shl	cx,1
		shl	cx,1
		shl	cx,1
		add	si,cx
		rept	2
		CgaTileLines	2000h-80+4
		endm
		movsw
		movsw
		add	di,bx
		movsw
		movsw
		jmp	@@exit

@@ega:		mov	bl,ah
		xor	bh,bh
		shl	bx,1
		mov	di,TileRowOfs[bx]
		xor	ah,ah
		shl	ax,1
		add	di,ax
		mov	dx,SC_INDEX
		mov	al,SC_MAPMASK
		out	dx,al
		inc	dx
		mov	al,0Fh
		out	dx,al
		mov	dx,GC_INDEX
		mov	al,GC_MODE
		out	dx,al
		inc	dx
		mov	al,1			; write mode 1
		out	dx,al
		mov	ax,EGA_SEG
		mov	es,ax
		cld
		cmp	bx,9*2
		je	@@egahalf
		mov	bp,TILECACHE_SEG
		mov	ds,bp
		xor	ch,ch
		shl	cx,1
		shl	cx,1
		shl	cx,1
		shl	cx,1
		shl	cx,1
		mov	si,cx
		mov	bx,40-2
		rept	15
		EgaTileLine
		endm
		movsb
		movsb
		mov	dx,GC_INDEX
		mov	al,GC_MODE
		out	dx,al
		inc	dx
		xor	al,al
		out	dx,al
		jmp	@@exit
@@egahalf:	mov	bp,TILECACHE_SEG
		mov	ds,bp
		xor	ch,ch
		shl	cx,1
		shl	cx,1
		shl	cx,1
		shl	cx,1
		shl	cx,1
		mov	si,cx
		mov	bx,40-2
		rept	5
		EgaTileLine
		endm
		movsb
		movsb
		mov	dx,GC_INDEX
		mov	al,GC_MODE
		out	dx,al
		inc	dx
		xor	al,al
		out	dx,al
		jmp	@@exit

@@vga:		mov	bl,ah
		xor	bh,bh
		shl	bx,1
		mov	di,VgaTileRowOfs[bx]
		xor	ah,ah
		shl	ax,1
		shl	ax,1
		shl	ax,1
		shl	ax,1
		add	di,ax
		mov	ax,EGA_SEG
		mov	es,ax
		cld
		cmp	bx,9*2
		jb	@@vgafull
		jmp	@@vgahalf
@@vgafull:	mov	bp,TilesSeg
		mov	ds,bp
		add	si,TilesOff
		mov	si,ds:[4]
		mov	ch,cl
		xor	cl,cl
		add	si,cx
		mov	bx,320-16
		rept	16
		VgaTileLine
		add	di,bx
		endm
		jmp	@@exit
@@vgahalf:	mov	bp,TilesSeg
		mov	ds,bp
		add	si,TilesOff
		mov	si,ds:[4]
		mov	ch,cl
		xor	cl,cl
		add	si,cx
		mov	bx,320-16
		rept	6
		VgaTileLine
		add	di,bx
		endm
		jmp	@@exit
DrawTileAt	endp

; void CacheEGATiles(void) -- F_95D1: copy the 53 tiles into EGA memory at
; A800:0000, 32 bytes per tile (16 lines x 2 bytes in each plane).
		public	_CacheEGATiles
_CacheEGATiles	proc	near
		mov	dx,SC_INDEX
		mov	al,SC_MAPMASK
		out	dx,al
		inc	dx
		mov	ax,TILECACHE_SEG
		mov	es,ax
		xor	di,di
		mov	ax,TilesSeg
		mov	ds,ax
		mov	si,ds:[4]
		cld
		mov	cx,NUM_TILES
@@tile:		push	cx
		mov	cx,16
@@line:		mov	ah,8
		mov	bx,di
@@plane:	mov	al,ah
		out	dx,al
		movsb
		movsb
		mov	di,bx
		shr	ah,1
		test	ah,0Fh
		jne	@@plane
		add	di,2
		loop	@@line
		pop	cx
		loop	@@tile
		mov	al,0Fh
		out	dx,al
		mov	ax,DGROUP
		mov	ds,ax
		ret
_CacheEGATiles	endp

		end

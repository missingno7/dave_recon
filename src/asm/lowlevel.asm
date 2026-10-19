; lowlevel.asm -- hand-written low-level services, first assembly module.
;
; Placement (verified by tools/match_asm.py):
; @at 0x6f26
; @seg _DATA 0x132e
;   _TEXT  cs [0x6f26, 0x7e59)  = file [0x7126, 0x8059), word aligned; TLINK
;          pads one 00 byte before it (cs 0x6f25) and one after it (cs 0x7e59).
;   _DATA  ds [0x132e, 0x13a9)
;
; Assembler: Turbo Assembler 2.0, single pass (no /m): forward `jmp` to a
; near label is emitted as EB xx 90, and the forward `call far ptr` in
; WaitSound comes out as 0E E8 xx xx 90 (see layout/assembler.json).
;
; Contents, in link order:
;   row-offset tables for CGA / EGA / VGA
;   PC-speaker sound driver on the timer interrupt (INT 8)
;   additive lagged-Fibonacci random number generator
;   vertical-retrace wait, EGA plane/mode helpers
;   8x8 font character drawing (CGA / EGA / VGA)
;   picture blitting through a size table (CGA / EGA latches / VGA)
;   video subsystem detection (Richard Wilton's VIDEO_ID, "Programmer's
;     Guide to PC & PS/2 Video Systems", adapted to return the type in AX)
;   RLE compressor / expander working on far buffers
;
; Census ids (F_XXXX = FILE offset) are noted on every procedure; C callers
; still refer to the procedures by those ids.

		.MODEL	small
		LOCALS

; ---------------------------------------------------------------- equates

GR_CGA		equ	1		; values of the C global GrMode
GR_EGA		equ	2
GR_VGA		equ	3

CGA_SEG		equ	0B800h
EGA_SEG		equ	0A000h

SC_INDEX	equ	3C4h		; EGA sequencer
SC_MAPMASK	equ	2
GC_INDEX	equ	3CEh		; EGA graphics controller
GC_READMAP	equ	4
GC_MODE		equ	5
CRT_STATUS	equ	3DAh		; input status #1, bit 3 = vertical retrace

PIC_CMD		equ	20h
EOI		equ	20h
PIT_CH0		equ	40h
PIT_CH2		equ	42h
PIT_CMD		equ	43h
PPI_B		equ	61h		; bits 0-1: speaker gate / data

DOS		equ	21h

; VIDEO_ID subsystem and display codes
MDA		equ	1
CGA		equ	2
EGA		equ	3
MCGA		equ	4
VGA		equ	5
HGC		equ	80h
HGCPlus		equ	81h
InColor		equ	82h
MDADisplay	equ	1
CGADisplay	equ	2
EGAColorDisplay	equ	3
PS2MonoDisplay	equ	4
PS2ColorDisplay	equ	5
TRUE		equ	1
FALSE		equ	0

VIDstruct	struc
Video0Type	db	?
Display0Type	db	?
Video1Type	db	?
Display1Type	db	?
VIDstruct	ends

Device0		equ	word ptr Video0Type[di]
Device1		equ	word ptr Video1Type[di]

; ------------------------------------------------------- C-owned globals

		.DATA
		extrn	_D_8604:word	; picture table: 16-byte entries {width, height, offset}
		extrn	_D_8A18:word	; segment of the 8x8 font
		extrn	_D_8A20:word	; segment of the picture data
		extrn	_D_8B32:word	; graphics mode (GR_CGA / GR_EGA / GR_VGA)

PicTable	equ	_D_8604
FontSeg		equ	_D_8A18
PicSeg		equ	_D_8A20
GrMode		equ	_D_8B32

; ------------------------------------------------------ module variables

		public	_SoundData, _SoundEnabled, _XorMask

RndIndex1	dw	0			; ds 132e  word index of the long lag
RndIndex2	dw	0			; ds 1330  word index of the short lag
RndTable	dw	18 dup (0)		; ds 1332  [0] = running sum, [1..17] state
RndInit		dw	1,1,2,3,5,8,13,21,54,75,129,204,323,527,850,1377,2227

TimerHooked	dw	0			; ds 1378  INT 8 handler installed
_SoundData	dd	0			; ds 137a  far table of 16-byte sound headers (set by C)
_SoundEnabled	dw	1			; ds 137e  low byte 0 = speaker muted
OldInt8		dd	0			; ds 1380
TickDivide	db	0			; ds 1384  chain the old INT 8 every n ticks
TickCount	db	0			; ds 1385
TimerRate	dw	0			; ds 1386  PIT channel 0 divisor (0 = 65536)
SoundPtr	dw	0			; ds 1388  next tone word, 0 = silent
SoundPriority	db	0			; ds 138a
SavedPtr	dw	0			; ds 138b  PauseSound / ResumeSound copy
SavedPriority	db	0
SavedDivide	db	0
SavedCount	db	0
SavedRate	dw	0

_XorMask	dw	0			; ds 1392  XORed into every font pixel

RleSegC		dw	0			; ds 1394  compressed buffer (segment, offset)
RleSegU		dw	0			; ds 1396  uncompressed buffer
RleOffC		dw	0			; ds 1398
RleOffU		dw	0			; ds 139a
RleLength	dd	0			; ds 139c  bytes left to consume / produce
RleOutLen	dd	0			; ds 13a0  compressed size produced
RleRun		dw	0			; ds 13a4  length of the pending run
RleByte		db	0			; ds 13a6  byte of the pending run
RleLiteral	dw	0			; ds 13a7  pending literal count

		.CODE

; ------------------------------------------------- row-offset tables (cs 6f26)

CgaRowOfs	label	word		; 200 lines, even lines in bank 0, odd in bank 1
y		=	0
		rept	100
		dw	y*80, 2000h+y*80
y		=	y+1
		endm

EgaRowOfs	label	word		; cs 70b6: 200 lines of 40 bytes
y		=	0
		rept	200
		dw	y*40
y		=	y+1
		endm

VgaRowOfs	label	word		; cs 7246: 200 lines of 320 bytes
y		=	0
		rept	200
		dw	y*320
y		=	y+1
		endm

; ======================================================= sound (cs 73d6)

; void StartSound(void) -- F_75D6: hook INT 8 (once) and enable the speaker.
		public	_StartSound
_StartSound	proc	near
		test	TimerHooked,0FFFFh
		jne	@@hooked
		call	_StopSound
		mov	ax,3500h+8		; get INT 8 vector
		int	DOS
		mov	word ptr OldInt8,bx
		mov	ax,es
		mov	word ptr OldInt8+2,ax
		mov	ax,1
		mov	TickDivide,al
		mov	TickCount,al
		push	ds
		push	cs
		pop	ds
		mov	dx,offset Int8ISR
		mov	ax,2500h+8		; set INT 8 vector
		int	DOS
		pop	ds
		inc	TimerHooked
@@hooked:	mov	ax,1
		mov	_SoundEnabled,ax
		ret
_StartSound	endp

; void ShutdownSound(void) -- F_760F: PIT back to 18.2 Hz, unhook INT 8.
		public	_ShutdownSound
_ShutdownSound	proc	near
		mov	al,36h			; channel 0, lo/hi, mode 3
		out	PIT_CMD,al
		mov	al,0
		out	PIT_CH0,al
		out	PIT_CH0,al
		mov	ax,TimerHooked
		cmp	ax,0
		je	@@done
		push	ds
		mov	dx,word ptr OldInt8
		mov	ax,word ptr OldInt8+2
		mov	ds,ax
		mov	ax,2500h+8
		int	DOS
		pop	ds
		mov	TimerHooked,0
		in	al,PPI_B
		and	al,0FDh			; speaker data off
		out	PPI_B,al
@@done:		ret
_ShutdownSound	endp

; void PlaySound(int n) -- F_763E: start sound n unless a higher-priority
; sound is playing. Header n (16 bytes at SoundData seg:n*16):
;   +0 offset of the tone list, +2 priority, +3 tick multiplier.
		public	_PlaySound
_PlaySound	proc	near
		push	bp
		mov	bp,sp
		mov	ax,[bp+4]
		push	si
		mov	si,ax
		shl	si,1
		shl	si,1
		shl	si,1
		shl	si,1
		mov	ax,word ptr _SoundData+2
		mov	es,ax
		mov	al,es:[si+2]
		cmp	al,SoundPriority
		jb	@@exit
		mov	SoundPriority,al
		mov	ax,es:[si]
		mov	SoundPtr,ax
		mov	bl,es:[si+3]
		mov	TickDivide,bl
		mov	TickCount,bl
		cmp	bl,1
		ja	@@fast
		xor	bx,bx			; 18.2 Hz
		jmp	@@setpit
@@fast:		xor	bh,bh			; divisor = 65536 / multiplier
		xor	ax,ax
		mov	dx,1
		div	bx
		mov	bx,ax
		mov	TimerRate,bx
@@setpit:	mov	al,36h
		out	PIT_CMD,al
		mov	al,bl
		out	PIT_CH0,al
		mov	al,bh
		out	PIT_CH0,al
@@exit:		pop	si
		pop	bp
		ret
_PlaySound	endp

; void StopSound(void) -- F_769B
		public	_StopSound
_StopSound	proc	near
		xor	ax,ax
		mov	SoundPtr,ax
		mov	SoundPriority,al
		mov	TimerRate,ax
		in	al,PPI_B
		and	al,0FDh
		out	PPI_B,al
		mov	al,36h
		out	PIT_CMD,al
		mov	al,0
		out	PIT_CH0,al
		out	PIT_CH0,al
		inc	al
		mov	TickDivide,al
		mov	TickCount,al
		ret
_StopSound	endp

; void PauseSound(void) -- F_76BF: remember the playing sound, then stop.
		public	_PauseSound
_PauseSound	proc	near
		mov	ax,SoundPtr
		mov	SavedPtr,ax
		mov	al,SoundPriority
		mov	SavedPriority,al
		mov	al,TickDivide
		mov	SavedDivide,al
		mov	al,TickCount
		mov	SavedCount,al
		mov	ax,TimerRate
		mov	SavedRate,ax
		call	_StopSound
		ret
_PauseSound	endp

; void ResumeSound(void) -- F_76E1
		public	_ResumeSound
_ResumeSound	proc	near
		mov	ax,SavedPtr
		mov	SoundPtr,ax
		mov	al,SavedPriority
		mov	SoundPriority,al
		mov	al,SavedDivide
		mov	TickDivide,al
		mov	al,SavedCount
		mov	TickCount,al
		mov	bx,SavedRate
		mov	al,36h
		out	PIT_CMD,al
		mov	al,bl
		out	PIT_CH0,al
		mov	al,bh
		out	PIT_CH0,al
		ret
_ResumeSound	endp

; void WaitSound(void) -- F_770A: run one tick by hand, then wait until the
; current sound has finished.
		public	_WaitSound
_WaitSound	proc	near
		pushf
		call	far ptr Int8ISR
@@wait:		mov	ax,SoundPtr
		cmp	ax,0
		jne	@@wait
		ret
_WaitSound	endp

; INT 8 handler -- F_7719. Plays one tone word per tick (0 = rest,
; -1 = end), chains to the BIOS handler every TickDivide ticks.
Int8ISR		proc	far
		push	ax
		push	bx
		push	cx
		push	si
		push	ds
		push	es
		mov	ax,DGROUP
		mov	ds,ax
		mov	ax,word ptr _SoundData+2
		mov	es,ax
		mov	al,EOI
		out	PIC_CMD,al
		dec	TickCount
		jnz	@@nochain
		mov	al,TickDivide
		mov	TickCount,al
		pushf
		call	OldInt8
@@nochain:	mov	si,SoundPtr
		cmp	si,0
		je	@@quiet
		mov	bx,es:[si]
		inc	SoundPtr
		inc	SoundPtr
		cmp	bx,0
		je	@@quiet
		cmp	bx,-1
		jne	@@tone
		call	_StopSound
		jmp	@@done
@@quiet:	in	al,PPI_B
		and	al,0FCh			; speaker off
		out	PPI_B,al
		jmp	@@done
@@tone:		test	_SoundEnabled,0FFh
		je	@@quiet
		mov	al,0B6h			; channel 2, lo/hi, mode 3
		out	PIT_CMD,al
		mov	al,bl
		out	PIT_CH2,al
		mov	al,bh
		out	PIT_CH2,al
		in	al,PPI_B
		or	al,3			; speaker on
		out	PPI_B,al
@@done:		pop	es
		pop	ds
		pop	si
		pop	cx
		pop	bx
		pop	ax
		iret
Int8ISR		endp

; ============================================= random numbers (cs 758c)

; void InitRnd(int randomize) -- F_778C
		public	_InitRnd
_InitRnd	proc	near
		push	bp
		mov	bp,sp
		push	si
		push	di
		mov	ax,[bp+4]
		cmp	ax,0
		jne	@@clock
		mov	dx,0
		mov	cx,dx
		mov	RndTable,dx
		jmp	@@seed
@@clock:	mov	ah,2Ch			; DOS get time
		int	DOS
@@seed:		mov	RndTable+2,dx
		mov	RndTable+4,cx
		mov	ax,17*2
		mov	RndIndex1,ax
		mov	ax,5*2
		mov	RndIndex2,ax
		mov	ax,ds
		mov	es,ax
		mov	di,offset RndTable+2
		mov	si,offset RndInit
		mov	cx,17
		cld
		rep	movsw
		mov	ax,0FFFFh
		push	ax
		call	_Random
		pop	ax
		mov	ax,0FFFFh
		push	ax
		call	_Random
		pop	ax
		pop	di
		pop	si
		pop	bp
		ret
_InitRnd	endp

; unsigned Random(unsigned max) -- F_77E1: returns 0..max.
		public	_Random
_Random		proc	near
		push	bp
		mov	bp,sp
		mov	ax,[bp+4]
		push	ax
		mov	dx,0FFFFh		; dx = smallest 2^k-1 covering max
@@mask:		shl	ax,1
		jb	@@gotmask
		shr	dx,1
		jmp	@@mask
@@gotmask:	pop	ax
		push	ax
		mov	bx,RndIndex1
		mov	si,RndIndex2
		mov	ax,RndTable[bx]
		adc	ax,RndTable[si]
		mov	RndTable[bx],ax
		add	ax,RndTable
		mov	RndTable,ax
		dec	bx
		dec	bx
		jne	@@1
		mov	bx,17*2
@@1:		dec	si
		dec	si
		jne	@@2
		mov	si,17*2
@@2:		mov	RndIndex1,bx
		mov	RndIndex2,si
		pop	cx
		and	ax,dx
		cmp	ax,cx
		jbe	@@ok
		shr	ax,1
@@ok:		pop	bp
		ret
_Random		endp

; ====================================================== video helpers

; void WaitVBL(void) -- F_7831
		public	_WaitVBL
_WaitVBL	proc	near
		push	si
		push	di
		mov	dx,CRT_STATUS
@@inretrace:	in	al,dx
		test	al,8
		jne	@@inretrace
@@waitretrace:	in	al,dx
		test	al,8
		je	@@waitretrace
		pop	di
		pop	si
		ret
_WaitVBL	endp

; void EGASelectPlane(int plane) -- F_7843: write mode 0, read and write
; the given plane only.
		public	_EGASelectPlane
_EGASelectPlane	proc	near
		push	bp
		mov	bp,sp
		mov	dx,GC_INDEX
		mov	ax,GC_MODE
		out	dx,ax
		mov	dx,GC_INDEX
		mov	al,GC_READMAP
		mov	ah,[bp+4]
		out	dx,ax
		mov	dx,SC_INDEX
		mov	al,SC_MAPMASK
		mov	ah,1
		mov	cl,[bp+4]
		shl	ah,cl
		out	dx,ax
		pop	bp
		ret
_EGASelectPlane	endp

; void EGALatchMode(void) -- F_7865: write mode 1 (latch copy), all planes.
		public	_EGALatchMode
_EGALatchMode	proc	near
		push	bp
		mov	bp,sp
		mov	dx,GC_INDEX
		mov	ax,0100h+GC_MODE
		out	dx,ax
		mov	dx,SC_INDEX
		mov	ax,0F00h+SC_MAPMASK
		out	dx,ax
		pop	bp
		ret
_EGALatchMode	endp

; ===================================================== font characters

; void DrawChar(int x, int y, int ch) -- F_7878: 8x8 character ch from the
; font segment at character cell (x, y), XORed with XorMask.
		public	_DrawChar
_DrawChar	proc	near
		push	bp
		mov	bp,sp
		push	si
		push	di
		mov	si,[bp+8]
		mov	di,[bp+4]
		mov	bx,[bp+6]
		shl	bx,1			; bx = y*8 lines * 2 bytes
		shl	bx,1
		shl	bx,1
		shl	bx,1
		mov	ax,GrMode
		cmp	ax,GR_CGA
		jne	@@notcga
		call	DrawCharCGA
		pop	di
		pop	si
		pop	bp
		ret
@@notcga:	cmp	ax,GR_EGA
		jne	@@notega
		call	DrawCharEGA
		pop	di
		pop	si
		pop	bp
		ret
@@notega:	cmp	ax,GR_VGA
		jne	@@done
		call	DrawCharVGA
@@done:		pop	di
		pop	si
		pop	bp
		ret
_DrawChar	endp

; CGA: 16 bytes per character, 2 bytes per line. -- F_78B5
DrawCharCGA	proc	near
		shl	si,1
		shl	si,1
		shl	si,1
		shl	si,1
		shl	di,1
		add	di,cs:CgaRowOfs[bx]
		mov	bx,_XorMask
		mov	ax,FontSeg
		mov	ds,ax
		mov	ax,CGA_SEG
		mov	es,ax
		cld
		rept	3
		lodsw				; even line
		xor	ax,bx
		stosw
		add	di,2000h-2		; to the odd bank
		lodsw				; odd line
		xor	ax,bx
		stosw
		sub	di,2000h-80+2		; back to the next even line
		endm
		lodsw
		xor	ax,bx
		stosw
		add	di,2000h-2
		lodsw
		xor	ax,bx
		stosw
		mov	ax,DGROUP
		mov	ds,ax
		ret
DrawCharCGA	endp

; one EGA font line: 1 byte, then down a 40-byte line
EgaCharLine	macro
		lodsb
		xor	al,dl
		stosb
		add	di,40-1
		endm

; EGA: 8 bytes per character, the same bitmap written to each plane in
; turn. -- F_7915
DrawCharEGA	proc	near
		shl	si,1
		shl	si,1
		shl	si,1
		add	di,cs:EgaRowOfs[bx]
		mov	cx,ds
		mov	ax,EGA_SEG
		mov	es,ax
		mov	dx,GC_INDEX
		mov	ax,GC_MODE		; write mode 0
		out	dx,ax
		cld
		mov	bx,si
		mov	cx,di
		mov	dx,GC_INDEX
		mov	ax,GC_READMAP		; plane 0
		out	dx,ax
		mov	dx,SC_INDEX
		mov	ax,0100h+SC_MAPMASK
		out	dx,ax
		mov	dx,_XorMask
		mov	ax,FontSeg
		mov	ds,ax
		rept	8
		EgaCharLine
		endm
plane		=	1
		rept	3
		mov	si,bx
		mov	di,cx
		push	dx
		mov	dx,GC_INDEX
		mov	ax,plane*100h+GC_READMAP
		out	dx,ax
		mov	dx,SC_INDEX
		mov	ax,(1 shl plane)*100h+SC_MAPMASK
		out	dx,ax
		pop	dx
		rept	8
		EgaCharLine
		endm
plane		=	plane+1
		endm
		mov	dx,SC_INDEX
		mov	ax,0F00h+SC_MAPMASK
		out	dx,ax
		mov	ax,DGROUP
		mov	ds,ax
		ret
DrawCharEGA	endp

; VGA (mode 13h): 64 bytes per character. -- F_7A73
DrawCharVGA	proc	near
		shl	si,1
		shl	si,1
		shl	si,1
		shl	si,1
		shl	si,1
		shl	si,1
		shl	di,1
		shl	di,1
		shl	di,1
		add	di,cs:VgaRowOfs[bx]
		mov	bx,_XorMask
		mov	ax,FontSeg
		mov	ds,ax
		mov	ax,EGA_SEG
		mov	es,ax
		cld
		rept	7
		rept	4
		lodsw
		xor	ax,bx
		stosw
		endm
		add	di,320-8
		endm
		rept	4
		lodsw
		xor	ax,bx
		stosw
		endm
		mov	ax,DGROUP
		mov	ds,ax
		ret
DrawCharVGA	endp

; ============================================================= pictures

; void DrawPic(int x, int y, int pic) -- F_7B3B: copy picture `pic` from
; the picture segment to the screen at pixel column x, line y.
		public	_DrawPic
_DrawPic	proc	near
		push	bp
		mov	bp,sp
		push	si
		push	di
		cld
		mov	si,[bp+8]
		shl	si,1
		shl	si,1
		shl	si,1
		shl	si,1
		mov	ax,PicTable[si]
		mov	cs:PicWidth,ax
		mov	ax,PicTable[si+2]
		mov	cs:PicHeight,ax
		mov	si,PicTable[si+4]
		mov	di,[bp+4]
		mov	bx,[bp+6]
		shl	bx,1
		mov	ax,GrMode
		mov	cx,PicSeg
		mov	ds,cx
		cmp	ax,GR_CGA
		jne	@@notcga
		call	DrawPicCGA
		jmp	@@done
@@notcga:	cmp	ax,GR_EGA
		jne	@@notega
		call	DrawPicEGA
		jmp	@@done
@@notega:	cmp	ax,GR_VGA
		jne	@@done
		call	DrawPicVGA
@@done:		mov	ax,DGROUP
		mov	ds,ax
		pop	di
		pop	si
		pop	bp
		ret
_DrawPic	endp

PicWidth	dw	0			; cs 7998  bytes per line
PicX		dw	0			; cs 799a  byte column on screen
PicHeight	dw	0			; cs 799c  lines left

; one picture line at a time: CX = width, DI = row start + PicX
PicCopy		macro	rows
		local	row, col
row:		mov	cx,cs:PicWidth
		mov	di,cs:rows[bx]
		add	bx,2
		add	di,cs:PicX
col:		movsb
		loop	col
		dec	cs:PicHeight
		jne	row
		endm

DrawPicCGA	proc	near			; F_7B9E
		shr	di,1
		shr	di,1
		mov	cs:PicX,di
		mov	ax,CGA_SEG
		mov	es,ax
		PicCopy	CgaRowOfs
		ret
DrawPicCGA	endp

DrawPicEGA	proc	near			; F_7BC9: VRAM-to-VRAM through the latches
		mov	ax,EGA_SEG
		mov	es,ax
		mov	ax,0100h+GC_MODE	; write mode 1
		mov	dx,GC_INDEX
		out	dx,ax
		shr	di,1
		shr	di,1
		shr	di,1
		mov	cs:PicX,di
		mov	ax,EGA_SEG
		mov	es,ax
		PicCopy	EgaRowOfs
		ret
DrawPicEGA	endp

DrawPicVGA	proc	near			; F_7C02
		mov	cs:PicX,di
		mov	ax,EGA_SEG
		mov	es,ax
		PicCopy	VgaRowOfs
		ret
DrawPicVGA	endp

; ====================================================== VIDEO_ID (cs 7a29)

		assume	ds:_TEXT		; VideoID runs with DS = CS

VIDinfo		VIDstruct <>			; cs 7a29

EGADisplays	db	CGADisplay		; 0000b, 0001b  (EGA switch values)
		db	EGAColorDisplay		; 0010b, 0011b
		db	MDADisplay		; 0100b, 0101b
		db	CGADisplay		; 0110b, 0111b
		db	EGAColorDisplay		; 1000b, 1001b
		db	MDADisplay		; 1010b, 1011b

DCCtable	db	0,0			; translate table for INT 10h func 1Ah
		db	MDA,MDADisplay
		db	CGA,CGADisplay
		db	0,0
		db	EGA,EGAColorDisplay
		db	EGA,MDADisplay
		db	0,0
		db	VGA,PS2MonoDisplay
		db	VGA,PS2ColorDisplay
		db	0,0
		db	MCGA,EGAColorDisplay
		db	MCGA,PS2MonoDisplay
		db	MCGA,PS2ColorDisplay

TestSequence	db	TRUE			; flag + routine, in test order
		dw	FindPS2
EGAflag		db	?
		dw	FindEGA
CGAflag		db	?
		dw	FindCGA
Monoflag	db	?
		dw	FindMono
NumberOfTests	equ	($-TestSequence)/3

; int VideoID(void) -- F_7C59: returns the active subsystem type
; (MDA / CGA / EGA / MCGA / VGA / HGC...) in AX.
		public	_VideoID
_VideoID	proc	near
		push	bp
		mov	bp,sp
		push	ds
		push	si
		push	di
		push	cs
		pop	ds
		mov	di,offset VIDinfo
		mov	Device0,0
		mov	Device1,0
		mov	CGAflag,TRUE
		mov	EGAflag,TRUE
		mov	Monoflag,TRUE
		mov	cx,NumberOfTests
		mov	si,offset TestSequence
@@next:		lodsb				; AL := flag
		test	al,al
		lodsw				; AX := subroutine address
		jz	@@skip
		push	si
		push	cx
		call	ax
		pop	cx
		pop	si
@@skip:		loop	@@next
		call	FindActive
		mov	al,VIDinfo.Video0Type
		mov	ah,0
		pop	di
		pop	si
		pop	ds
		mov	sp,bp
		pop	bp
		ret
_VideoID	endp

FindPS2		proc	near			; MCGA / VGA through INT 10h AX=1A00h
		mov	ax,1A00h
		int	10h
		cmp	al,1Ah
		jne	@@exit			; function not supported
		mov	cx,bx
		xor	bh,bh			; BX := DCC for active subsystem
		or	ch,ch
		jz	@@one			; only one subsystem present
		mov	bl,ch			; BX := inactive DCC
		add	bx,bx
		mov	ax,word ptr DCCtable[bx]
		mov	Device1,ax
		mov	bl,cl
		xor	bh,bh			; BX := active DCC
@@one:		add	bx,bx
		mov	ax,word ptr DCCtable[bx]
		mov	Device0,ax
		mov	CGAflag,FALSE
		mov	EGAflag,FALSE
		mov	Monoflag,FALSE
		lea	bx,Video0Type[di]	; if the BIOS reported an MDA ...
		cmp	byte ptr [bx],MDA
		je	@@mda
		lea	bx,Video1Type[di]
		cmp	byte ptr [bx],MDA
		jne	@@exit
@@mda:		mov	word ptr [bx],0		; ... Hercules can't be ruled out
		mov	Monoflag,TRUE
@@exit:		ret
FindPS2		endp

FindEGA		proc	near			; INT 10h AH=12h BL=10h
		mov	bl,10h
		mov	ah,12h
		int	10h
		cmp	bl,10h
		je	@@exit			; no EGA BIOS
		mov	al,cl
		shr	al,1			; AL := switches/2
		mov	bx,offset EGADisplays
		xlat
		mov	ah,al			; AH := display type
		mov	al,EGA
		call	FoundDevice
		cmp	ah,MDADisplay
		je	@@mono
		mov	CGAflag,FALSE		; no CGA if the EGA has a color display
		jmp	short @@exit
@@mono:		mov	Monoflag,FALSE		; EGA on a mono display: no MDA / HGC
@@exit:		ret
FindEGA		endp

FindCGA		proc	near
		mov	dx,3D4h			; CRTC address port
		call	Find6845
		jc	@@exit
		mov	al,CGA
		mov	ah,CGADisplay
		call	FoundDevice
@@exit:		ret
FindCGA		endp

FindMono	proc	near
		mov	dx,3B4h			; CRTC address port
		call	Find6845
		jc	@@exit
		mov	dl,0BAh			; DX := 3BAh (status port)
		in	al,dx
		and	al,80h
		mov	ah,al			; AH := bit 7 (vertical sync on HGC)
		mov	cx,8000h
@@sync:		in	al,dx
		and	al,80h
		cmp	ah,al
		loope	@@sync			; wait for bit 7 to change
		jne	@@herc
		mov	al,MDA			; bit 7 never changed: MDA
		mov	ah,MDADisplay
		call	FoundDevice
		jmp	short @@exit
@@herc:		in	al,dx
		mov	dl,al
		and	dl,01110000b		; Hercules id bits
		mov	ah,MDADisplay
		mov	al,HGCPlus
		cmp	dl,00010000b
		je	@@found
		mov	al,HGC
		cmp	dl,01010000b
		jne	@@found
		mov	al,InColor
		mov	ah,EGAColorDisplay
@@found:	call	FoundDevice
@@exit:		ret
FindMono	endp

Find6845	proc	near			; DX = CRTC port; CF set if absent
		mov	al,0Fh
		out	dx,al			; select register 0Fh (cursor low)
		inc	dx
		in	al,dx
		mov	ah,al			; preserve the old value
		mov	al,66h
		out	dx,al			; try to write it
		mov	cx,100h
@@delay:	loop	@@delay
		in	al,dx
		xchg	ah,al			; AH := value read back
		out	dx,al			; restore the old value
		cmp	ah,66h
		je	@@exit			; it responded (CF clear)
		stc
@@exit:		ret
Find6845	endp

FindActive	proc	near			; make Device0 the active subsystem
		cmp	Device1,0
		je	@@exit			; only one subsystem
		cmp	Video0Type[di],4
		jge	@@exit			; MCGA / VGA: BIOS already decided
		cmp	Video1Type[di],4
		jge	@@exit
		mov	ah,0Fh
		int	10h			; AL := current video mode
		and	al,7
		cmp	al,7
		je	@@monomode
		cmp	Display0Type[di],MDADisplay
		jne	@@exit			; Display0 is color
		jmp	short @@swap
@@monomode:	cmp	Display0Type[di],MDADisplay
		je	@@exit			; Display0 is monochrome
@@swap:		mov	ax,Device0
		xchg	ax,Device1
		mov	Device0,ax
@@exit:		ret
FindActive	endp

FoundDevice	proc	near			; AL = subsystem, AH = display
		lea	bx,Video0Type[di]
		cmp	byte ptr [bx],0
		je	@@store			; first subsystem
		lea	bx,Video1Type[di]
@@store:	mov	[bx],ax
		ret
FoundDevice	endp

		assume	ds:nothing, ss:DGROUP	; RLE: DS is free, variables through SS

; ====================================================== RLE (cs 7bc5)
;
; Compressed stream: a code byte n < 80h means n+3 copies of the next
; byte; n >= 80h means n-7Fh literal bytes follow.

; long RLECompress(void far *src, long len, void far *dst) -- file 7dc5:
; returns the compressed size.
		public	_RLECompress
_RLECompress	proc	near
		push	bp
		mov	bp,sp
		mov	ax,[bp+4]
		mov	RleOffU,ax
		mov	ax,[bp+6]
		mov	RleSegU,ax
		mov	ax,[bp+12]
		mov	RleOffC,ax
		mov	ax,[bp+14]
		mov	RleSegC,ax
		mov	ax,[bp+8]
		mov	word ptr RleLength,ax
		mov	ax,[bp+10]
		mov	word ptr RleLength+2,ax
		call	RleCompressCore
		mov	ax,word ptr RleOutLen
		mov	dx,word ptr RleOutLen+2
		pop	bp
		ret
_RLECompress	endp

; void RLEExpand(void far *src, void far *dst, long len) -- F_7E00
		public	_RLEExpand
_RLEExpand	proc	near
		push	bp
		mov	bp,sp
		mov	ax,[bp+4]
		mov	RleOffC,ax
		mov	ax,[bp+6]
		mov	RleSegC,ax
		mov	ax,[bp+8]
		mov	RleOffU,ax
		mov	ax,[bp+10]
		mov	RleSegU,ax
		mov	ax,[bp+12]
		mov	word ptr RleLength,ax
		mov	ax,[bp+14]
		mov	word ptr RleLength+2,ax
		call	RleExpandCore
		pop	bp
		ret
_RLEExpand	endp

RleSetup	proc	near			; F_7E32: SI = uncompressed, DI = compressed
		mov	RleRun,0
		mov	RleLiteral,1
		mov	word ptr RleOutLen,0
		mov	word ptr RleOutLen+2,0
		mov	si,RleOffU
		mov	di,RleOffC
		ret
RleSetup	endp

WriteRun	proc	near			; file 7e59: emit the pending run
		push	si
		push	es
		push	ax
		mov	es,RleSegC
		mov	ax,RleRun
		sub	al,2
		stosb
		mov	al,RleByte
		stosb
		mov	si,RleOffU
		inc	si
		add	si,RleRun
		mov	RleOffU,si
		add	word ptr RleOutLen,2
		adc	word ptr RleOutLen+2,0
		mov	RleRun,0
		pop	ax
		pop	es
		pop	si
		ret
WriteRun	endp

WriteLiterals	proc	near			; file 7e94: emit the pending literals
		push	es
		push	ax
		push	si
		mov	es,RleSegC
		mov	ax,RleLiteral
		add	al,7Fh
		stosb
		mov	cx,RleLiteral
		mov	ax,cx
		inc	ax
		add	word ptr RleOutLen,ax
		adc	word ptr RleOutLen+2,0
		mov	si,RleOffU
		push	ds
		mov	ds,RleSegU
		rep	movsb
		pop	ds
		mov	RleLiteral,0
		mov	RleOffU,si
		pop	si
		pop	ax
		pop	es
		ret
WriteLiterals	endp

RleExpandCore	proc	near			; F_7ED4
		call	RleSetup
		xchg	si,di			; SI = compressed, DI = output
		mov	dx,1
@@reseg:	mov	es,RleSegU
		xor	ah,ah
@@next:		cmp	di,0FF00h
		jb	@@code
		mov	ax,di			; renormalize both far pointers
		shr	ax,1
		shr	ax,1
		shr	ax,1
		shr	ax,1
		add	RleSegU,ax
		mov	di,0
		mov	ax,si
		shr	ax,1
		shr	ax,1
		shr	ax,1
		shr	ax,1
		add	RleSegC,ax
		and	si,0Fh
		jmp	@@reseg
@@code:		sub	word ptr RleLength,dx
		sbb	word ptr RleLength+2,0
		jb	@@done
		xor	dx,dx
		push	ds
		mov	ds,RleSegC
		lodsb
		cmp	al,80h
		jb	@@run
		sub	al,7Fh			; literal block
		mov	cx,ax
		mov	dx,ax
		rep	movsb
		pop	ds
		jmp	@@next
@@run:		add	al,3			; run
		mov	cx,ax
		mov	dx,ax
		lodsb
		rep	stosb
		pop	ds
		jmp	@@next
@@done:		ret
RleExpandCore	endp

RleCompressCore	proc	near			; file 7f41
		call	RleSetup
@@reseg:	mov	es,RleSegU
		mov	al,es:[si]
		mov	RleByte,al
@@next:		cmp	si,0FF00h
		jb	@@byte
		call	FlushRle		; renormalize both far pointers
		mov	ax,si
		shr	ax,1
		shr	ax,1
		shr	ax,1
		shr	ax,1
		add	RleSegU,ax
		and	si,0Fh
		mov	RleOffU,0
		mov	ax,di
		shr	ax,1
		shr	ax,1
		shr	ax,1
		shr	ax,1
		add	RleSegC,ax
		and	di,0Fh
		inc	RleLiteral
		jmp	@@reseg
@@byte:		sub	word ptr RleLength,1
		sbb	word ptr RleLength+2,0
		jnc	@@more
		jmp	FlushRle		; input exhausted
@@more:		inc	si
		mov	al,es:[si]
		cmp	al,RleByte
		jne	@@differs
		inc	RleRun
		cmp	RleRun,2
		jb	@@next
		cmp	RleLiteral,1
		jbe	@@nolits
		dec	RleLiteral
		call	WriteLiterals
@@nolits:	mov	RleLiteral,0
		cmp	RleRun,81h
		jb	@@again
		call	WriteRun		; run is full
		cmp	al,es:[si+1]
		jne	@@again
		cmp	al,es:[si+2]
		jne	@@again
		inc	si
@@again:	jmp	@@next
@@differs:	mov	cx,RleRun
		jcxz	@@literal
		cmp	cx,2
		jb	@@shortrun
		call	WriteRun
		jmp	short @@literal
@@shortrun:	add	RleLiteral,cx		; a 2-byte repeat stays literal
		mov	RleRun,0
@@literal:	inc	RleLiteral
		mov	RleByte,al
		cmp	RleLiteral,7Eh
		jb	@@again2
		call	WriteLiterals		; literal block is full
		cmp	al,es:[si+1]
		jne	@@again2
		cmp	al,es:[si+2]
		jne	@@again2
		inc	si
		inc	RleLiteral
@@again2:	jmp	@@next
RleCompressCore	endp

FlushRle	proc	near			; file 802d: emit whatever is pending
		mov	cx,RleRun
		jcxz	@@lits
		cmp	cx,2
		jb	@@shortrun
		cmp	RleLiteral,1
		jb	@@run
		call	WriteLiterals
@@run:		call	WriteRun
		jmp	short @@exit
@@shortrun:	add	RleLiteral,cx
@@lits:		mov	cx,RleLiteral
		jcxz	@@exit
		call	WriteLiterals
@@exit:		ret
FlushRle	endp

		end

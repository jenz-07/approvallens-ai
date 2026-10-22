import io, re, warnings
import pymupdf as fitz
import pytesseract
from PIL import Image
from .config import settings

FIELDS = {'institution_name':'Institution Name', 'institution_identifier':'Institution Identifier', 'address':'Address', 'issuing_authority':'Issuing Authority', 'reference_number':'Reference Number', 'issue_date':'Issue Date', 'expiry_date':'Expiry Date', 'academic_year':'Academic Year', 'programme':'Programme', 'intake':'Intake', 'document_type':'Document Type'}
def inspect_file(data, filename, mime):
    ext = filename.rsplit('.', 1)[-1].lower()
    if len(data) > settings.max_file_mb*1024*1024: raise ValueError('File exceeds configured size limit')
    if ext == 'pdf' and mime == 'application/pdf' and data.startswith(b'%PDF-'):
        try:
            with fitz.open(stream=data, filetype='pdf') as doc:
                if doc.needs_pass: raise ValueError('Password-protected PDF: upload an unencrypted copy')
                if not 1 <= len(doc) <= settings.max_pages: raise ValueError('PDF page limit exceeded or empty PDF')
                for page in doc:
                    if page.rect.width*page.rect.height*(150/72)**2 > settings.max_image_pixels: raise ValueError('PDF page is too large to render safely')
                return len(doc)
        except ValueError: raise
        except Exception: raise ValueError('Unreadable PDF; export a new PDF and retry')
    expected = {'png':('image/png','PNG'), 'jpg':('image/jpeg','JPEG'), 'jpeg':('image/jpeg','JPEG')}
    if ext not in expected or mime != expected[ext][0]: raise ValueError('Use a PDF, PNG or JPEG with a matching MIME type')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as im:
                if im.format != expected[ext][1] or im.width*im.height > settings.max_image_pixels: raise ValueError('Image format mismatch or dimensions exceed limit')
                im.verify()
    except Exception: raise ValueError('Unreadable image or image dimensions exceed limit')
    return 1

def ocr(im):
    d = pytesseract.image_to_data(im, config='--psm 6', output_type=pytesseract.Output.DICT, timeout=45)
    words=[]; lines={}
    for i, text in enumerate(d['text']):
        if not text.strip(): continue
        key=(d['block_num'][i], d['par_num'][i], d['line_num'][i])
        lines.setdefault(key, []).append(text)
        x,y,w,h=[d[k][i] for k in ('left','top','width','height')]
        words.append({'text':text,'bbox':[x/im.width,y/im.height,(x+w)/im.width,(y+h)/im.height],'confidence':float(d['conf'][i])})
    return '\n'.join(' '.join(x) for x in lines.values()),words

def extract(data, mime):
    pages=[]
    if mime == 'application/pdf':
        with fitz.open(stream=data, filetype='pdf') as doc:
            for n,p in enumerate(doc):
                text=p.get_text('text'); method='native_pdf'; words=[]
                if len(text.strip()) < 30:
                    pix=p.get_pixmap(matrix=fitz.Matrix(150/72,150/72), alpha=False)
                    im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
                    text,words=ocr(im); method='tesseract'
                else:
                    words=[{'text':w[4], 'bbox':[w[0]/p.rect.width,w[1]/p.rect.height,w[2]/p.rect.width,w[3]/p.rect.height], 'confidence':None} for w in p.get_text('words')]
                pages.append({'page':n+1,'text':text,'words':words,'method':method})
    else:
        with Image.open(io.BytesIO(data)) as im: text,words=ocr(im.convert('RGB'))
        pages=[{'page':1,'text':text,'words':words,'method':'tesseract'}]
    fields=parse_fields(pages)
    return pages,fields

ALIASES={
    'institution_name':['Institution Name','College Name'],
    'institution_identifier':['Institution Identifier','Institution ID','Institution Code'],
    'reference_number':['Reference Number','Certificate Number','Certificate No.'],
    'expiry_date':['Expiry Date','Valid Until'],
}

def parse_fields(pages):
    fields=[]
    for p in pages:
        for name,label in FIELDS.items():
            labels=ALIASES.get(name,[label])
            pattern=r'^[ \t]*(?:'+ '|'.join(re.escape(x) for x in labels) +r')[ \t]*:[ \t]*([^\n\r]+)'
            matches=list(re.finditer(pattern,p['text'],re.I|re.M))
            matches=[m for m in matches if m.group(1).strip()]
            if not matches:continue
            values=list(dict.fromkeys(m.group(1).strip() for m in matches))
            value=values[0] if len(values)==1 else None
            excerpt=' | '.join(m.group(0).strip() for m in matches)
            if value is None:excerpt='Conflicting values on this page: '+excerpt
            # Use a phrase box only if the exact token sequence is unique on this page.
            tokens=value.split() if value else []
            candidates=[]
            if tokens:
                for i in range(len(p['words'])-len(tokens)+1):
                    span=p['words'][i:i+len(tokens)]
                    if [w['text'] for w in span]==tokens:candidates.append(span)
            span=candidates[0] if len(candidates)==1 else []
            bbox=[min(w['bbox'][0] for w in span),min(w['bbox'][1] for w in span),max(w['bbox'][2] for w in span),max(w['bbox'][3] for w in span)] if span else None
            confidence=span[0].get('confidence') if len(span)==1 and p['method']=='tesseract' else None
            fields.append({'name':name,'value':value,'page':p['page'],'bbox':bbox,'excerpt':excerpt,'method':p['method'],'ocr_confidence':confidence})
    return fields

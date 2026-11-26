# Lossless / quality-preserving batch PDF compressor for DPR PDFs
# Uses pypdf (compress_identical_objects + compress_content_streams) so text,
# vector graphics, and embedded images are preserved with zero visual quality loss.
# Note: tooladda-online/pdf-compress (https://tooladda.online/pdf-compress.html)
# is a browser-only web tool with no installable library/API; this script provides
# automated local batch compression for the downloaded DPR archive.

import os
import sys
import csv
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pypdf import PdfReader, PdfWriter

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

BASE_DIR = os.path.join(os.path.expanduser('~'), 'Desktop', 'Mla funds', 'Portal_Documents')
SRC_DIR  = os.path.join(BASE_DIR, 'DPR_PDFs')
OUT_DIR  = os.path.join(BASE_DIR, 'DPR_PDFs_Compressed')
LOG_PATH = os.path.join(BASE_DIR, 'compression_log.csv')

MIN_SIZE_BYTES = 100 * 1024  # Compress PDFs > 100 KB; copy smaller ones as-is
MAX_WORKERS    = 6


def compress_one(src_path: str, dst_path: str) -> tuple[str, int, int, str]:
    orig_size = os.path.getsize(src_path)
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)

    if os.path.exists(dst_path) and os.path.getsize(dst_path) > 0:
        return src_path, orig_size, os.path.getsize(dst_path), 'skipped_exists'

    if orig_size < MIN_SIZE_BYTES:
        with open(src_path, 'rb') as rf, open(dst_path, 'wb') as wf:
            wf.write(rf.read())
        return src_path, orig_size, orig_size, 'copied_small'

    try:
        reader = PdfReader(src_path)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        for page in writer.pages:
            page.compress_content_streams()
        writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)

        tmp_path = dst_path + '.tmp'
        with open(tmp_path, 'wb') as f:
            writer.write(f)

        comp_size = os.path.getsize(tmp_path)
        if comp_size < orig_size and comp_size > 100:
            os.replace(tmp_path, dst_path)
            return src_path, orig_size, comp_size, 'compressed'
        else:
            os.remove(tmp_path)
            with open(src_path, 'rb') as rf, open(dst_path, 'wb') as wf:
                wf.write(rf.read())
            return src_path, orig_size, orig_size, 'kept_original'
    except Exception as e:
        tmp_path = dst_path + '.tmp'
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        with open(src_path, 'rb') as rf, open(dst_path, 'wb') as wf:
            wf.write(rf.read())
        return src_path, orig_size, orig_size, f'fallback_copy:{str(e)[:60]}'


def main():
    if not os.path.isdir(SRC_DIR):
        print(f'Source directory not found: {SRC_DIR}')
        return

    pdfs = []
    for root, _, files in os.walk(SRC_DIR):
        for fn in files:
            if fn.lower().endswith('.pdf'):
                src_p = os.path.join(root, fn)
                rel_p = os.path.relpath(src_p, SRC_DIR)
                dst_p = os.path.join(OUT_DIR, rel_p)
                pdfs.append((src_p, dst_p))

    print(f'Found {len(pdfs)} PDFs in {SRC_DIR}')
    os.makedirs(OUT_DIR, exist_ok=True)

    t0 = time.time()
    total_orig = 0
    total_comp = 0
    done = 0

    with open(LOG_PATH, 'w', newline='', encoding='utf-8-sig') as lf:
        writer = csv.writer(lf)
        writer.writerow(['Relative Path', 'Original Bytes', 'Compressed Bytes', 'Saved Bytes', 'Saved %', 'Status'])

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(compress_one, s, d): (s, d) for s, d in pdfs}
            for fut in as_completed(futures):
                src_p, orig_b, comp_b, status = fut.result()
                rel_p = os.path.relpath(src_p, SRC_DIR)
                saved_b = orig_b - comp_b
                saved_pct = (saved_b / orig_b * 100) if orig_b > 0 else 0.0
                writer.writerow([rel_p, orig_b, comp_b, saved_b, f'{saved_pct:.2f}%', status])
                total_orig += orig_b
                total_comp += comp_b
                done += 1
                if done % 100 == 0 or done == len(pdfs):
                    elapsed = time.time() - t0
                    saved_mb = (total_orig - total_comp) / (1024 * 1024)
                    print(f'[{done}/{len(pdfs)}] Orig: {total_orig/1048576:.1f} MB -> Comp: {total_comp/1048576:.1f} MB | Saved: {saved_mb:.1f} MB ({elapsed:.1f}s)')

    pct_total = ((total_orig - total_comp) / total_orig * 100) if total_orig > 0 else 0.0
    print(f'Done! Total: {total_orig/1048576:.1f} MB -> {total_comp/1048576:.1f} MB (Saved {pct_total:.1f}%). Log: {LOG_PATH}')


if __name__ == '__main__':
    main()

EXPORTS = [('drt', 'EXPORT_DRT', 'EXPORT_NONE'), ('fcpxml', 'EXPORT_FCPXML_1_10', 'EXPORT_NONE'), ('otio', 'EXPORT_OTIO', 'EXPORT_NONE'),
           ('aaf', 'EXPORT_AAF', 'EXPORT_AAF_NEW'), ('edl', 'EXPORT_EDL', 'EXPORT_NONE'), ('csv', 'EXPORT_TEXT_CSV', 'EXPORT_NONE')]
def export_all(tl, tag, ED):
    out = {}
    for ext, t, st in EXPORTS:
        p = '%s/%s.%s' % (ED, tag, ext)
        out[ext] = js(call(tl, 'Export', p, getattr(resolve, t), getattr(resolve, st)))
    return out

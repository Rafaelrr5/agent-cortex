"""Build local materials from authored generic JSON; no external writes."""
import argparse
import copy
import html
import json
from pathlib import Path
import sys

def render(data):
    if not isinstance(data.get('title'),str) or not data['title']:
        raise ValueError('nonempty title required')
    if not isinstance(data.get('slides'),list) or not data['slides']:
        raise ValueError('slides required')
    learning = [s for s in data['slides'] if s.get('kind')=='learning']
    agenda = [s for s in data['slides'] if s.get('kind')=='agenda']
    if len(learning)!=1 or len(agenda)!=1:
        raise ValueError('one learning and one agenda slide required')
    for s in data['slides']:
        if s.get('kind') not in ('learning','agenda') or not isinstance(s.get('title'),str) or not isinstance(s.get('items'),list) or not s['items'] or not all(isinstance(x,str) for x in s['items']):
            raise ValueError('invalid slide')
    if not data.get('quiz'): raise ValueError('quiz required')
    quiz = []
    for q in data['quiz']:
        choices = q.get('choices')
        if not isinstance(q.get('question'),str) or not isinstance(choices,list) or len(choices)<2 or not all(isinstance(x,str) for x in choices):
            raise ValueError('invalid question')
        for key, maximum in [('answer',len(choices)),('learning_index',len(learning[0]['items']))]:
            if type(q.get(key)) is not int or not 0<=q[key]<maximum:
                raise ValueError('invalid '+key)
        quiz.append(dict(q, explanation=learning[0]['items'][q['learning_index']]))
    esc=html.escape
    head='<!doctype html><html lang="en"><meta charset="utf-8"><title>'+esc(data['title'])+'</title>'
    section=lambda s:'<section class="slide"><h2>'+esc(s['title'])+'</h2><ul>'+''.join('<li>'+esc(x)+'</li>' for x in s['items'])+'</ul></section>'
    body=''.join(section(s) for s in data['slides'])
    style='<style>body{margin:0}.slide{width:1280px;height:720px;padding:64px;box-sizing:border-box;font:32px system-ui;break-after:page}@page{size:13.333333in 7.5in;margin:0}</style>'
    summary=head+'<h1>'+esc(data['title'])+'</h1>'+body
    review=summary+'<h2>Answer key</h2>'+''.join('<p>'+esc(q['question'])+' <strong>'+esc(q['choices'][q['answer']])+'</strong> '+esc(q['explanation'])+'</p>' for q in quiz)
    return {'slides.html':head+style+body+'</html>','summary.html':summary+'</html>','quiz.json':json.dumps(quiz,indent=2)+'\n','review.html':review+'</html>'}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--source',type=Path)
    args=parser.parse_args()
    home=Path(__file__).resolve().parents[1]
    try:
        data=json.loads((args.source or home/'fixtures/edition-example.json').read_text(encoding='utf-8'))
        outputs=render(data)
        if args.self_test:
            assert outputs['slides.html'].count('<section')==len(data['slides'])
            changed=copy.deepcopy(data)
            changed['slides'][1]['items'][0]='New <learning> & result'
            check=render(changed)
            assert 'New &lt;learning&gt; &amp; result' in check['slides.html'] and 'New &lt;learning&gt; &amp; result' in check['summary.html']
            assert json.loads(check['quiz.json'])[0]['explanation']=='New <learning> & result'
            for field in ('title','slides','answer'):
                bad=copy.deepcopy(data)
                if field=='answer': bad['quiz'][0]['answer']=99
                else: del bad[field]
                try: render(bad)
                except ValueError: continue
                raise AssertionError('negative test stayed green')
            print('PASS: section count, shared-source update, HTML escaping; 3 invalid fixtures rejected')
    except (ValueError,OSError,KeyError,TypeError) as error:
        print('Invalid source: '+str(error),file=sys.stderr)
        return 1
    out=home/'outputs'
    out.mkdir(exist_ok=True)
    for name,text in outputs.items(): (out/name).write_text(text,encoding='utf-8')
    print('Generated slides.html, summary.html, quiz.json, review.html')
    return 0
if __name__=='__main__': sys.exit(main())

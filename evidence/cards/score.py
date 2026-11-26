import json,re,sys,collections
d=sys.argv[1] if len(sys.argv)>1 else '.'
cards=json.load(open(f'{d}/cards_shuffled.json'))
tot=need=rec=recn=unk=unk2=0; words=collections.Counter()
for i in (1,2,3):
    r=json.load(open(f'{d}/reader{i}.json'))['result']
    m=re.search(r'\[.*\]',r,re.S); ans=json.loads(m.group(0))
    for a in ans:
        c=cards[a['card']-1]; tot+=1
        want='yes' if c['who']=='you' else 'no'
        need+= a['need_me']==want
        if want=='yes':
            recn+=1; s=a['i_would_say'].lower()
            act=c['action'].lower()
            ok=('reject' in act and ('no' in s.split() or 'reject' in s or "don't" in s or 'fix' in s)) or ('reject' not in act)
            rec+=ok
        u=a.get('unknown_words') or []
        if u: unk+=1
        helper=' '.join(l for l in c['text'].splitlines() if 'For the helper' in l).lower()
        u2=[w for w in u if w.lower() not in helper]
        if u2: unk2+=1
        words.update(w.lower() for w in u)
print(f'need_me {need}/{tot}  rec {rec}/{recn}  unknown-any {unk}/{tot} ({100*unk/tot:.1f}%)  excl-helper-lines {unk2}/{tot} ({100*unk2/tot:.1f}%)')
print(words.most_common(25))
miss=collections.Counter()
for i in (1,2,3):
    r=json.load(open(f'{d}/reader{i}.json'))['result']; ans=json.loads(re.search(r'\[.*\]',r,re.S).group(0))
    for a in ans:
        c=cards[a['card']-1]; want='yes' if c['who']=='you' else 'no'
        if a['need_me']!=want: miss[c['id']]+=1
print('misses',dict(miss))

"""Reprice frozen TradeDay HY3 orders against displayed annual NQ liquidity."""

from argparse import ArgumentParser
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from csv import DictReader, reader
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from sqx_tradeday_fast_pass import NQ, ROOT, digest, read, write_json


OUT = ROOT.parent / 'TradeDay-TBBO-Ausfuehrung'
PORTFOLIO_OUT = OUT / 'Fast-Pass-bis-5-Konten'
FUNDED = 'SMA5/10 nach Außenbruch'
SOURCE = Path(__file__).with_suffix('.cpp')


def reconstruct(*, portfolio=False):
    reference = read(ROOT / 'Ergebnisse.json')
    proofs = reference['proofs']
    output = PORTFOLIO_OUT if portfolio else OUT
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='sqx-td-liquidity-') as temp, ThreadPoolExecutor(5) as pool:
        work = Path(temp)
        binary = work / 'liquidity'
        subprocess.run(['clang++', '-O3', '-std=c++17', '-Wall', '-Wextra', str(SOURCE), '-lz', '-o', str(binary)],
                       check=True)

        def segment(item):
            symbol, proof = item
            tape = NQ.out / 'Basisdaten' / symbol
            schedule = work / f'{symbol}.orders'
            receipts = []
            with schedule.open('w') as out:
                for phase, label in enumerate(('EMA20', FUNDED), 1):
                    source = proof['cases'][label]
                    fill = Path(source['fills'])
                    if digest(fill) != source['sha256']:
                        raise ValueError(f'Invalid SQX receipt for {symbol}/{label}')
                    with fill.open(newline='') as stream:
                        for t in DictReader(stream):
                            side = {'LONG': 1, 'SHORT': -1}[t['side']]
                            for kind, direction in (('entry', side), ('exit', -side)):
                                price = int(t[f'{kind}_price_cents'])
                                if price % 25:
                                    raise ValueError('Outside the NQ price grid')
                                print(phase, t[f'{kind}_time_ns'], direction, price // 25, int(kind == 'entry'), file=out)
                    receipts.append(source['sha256'])
            stage = read(tape / 'staged.json')
            if stage['callbacks'] != proof['callbacks']:
                raise ValueError(f'TBBO callback count differs from the native SQX run: {symbol}')
            target = output / f'Quote-Pfade-{symbol}.csv'
            pending = target.with_suffix('.part')
            with pending.open('w') as stream:
                command = [str(binary), str(tape / 'tape.csv.gz'), str(tape / 'quotes.csv'), str(schedule),
                           str(stage['callbacks'])]
                if portfolio:
                    command.append('--portfolio')
                subprocess.run(command, stdout=stream, check=True)
            pending.replace(target)
            print(f'{symbol}: shared liquidity paths verified', flush=True)
            return symbol, dict(marks=str(target), callbacks=stage['callbacks'], marks_sha256=digest(target),
                                fills_sha256=receipts)

        records = dict(pool.map(segment, proofs.items()))
    write_json(output / 'Quote-Pfade-Nachweis.json', dict(source_sha256=digest(SOURCE), segments=records))


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--portfolio', action='store_true', help='Test up to five active accounts with up to four NQ each')
    reconstruct(portfolio=parser.parse_args().portfolio)

# Python MapReduce WordCount

The mapper reads text from standard input, splits each line on whitespace, and emits `word\t1`. Hadoop Streaming sorts mapper output by key before passing it to the reducer. The reducer aggregates adjacent equal keys and writes `word\ttotal`.

## Files

- `mapper.py` - emits one count record per token.
- `reducer.py` - sums values for each sorted token.
- `test_wordcount.py` - tests mapper, reducer, and the complete local pipeline.

## Local verification

```bash
python3 -m py_compile mapper.py reducer.py test_wordcount.py
python3 -m unittest -v test_wordcount.py
```

## Native Hadoop Streaming execution

Run from this directory on the configured Hadoop host:

```bash
hadoop jar /usr/local/hadoop/share/hadoop/tools/lib/hadoop-streaming-3.3.1.jar \
  -D mapreduce.job.name=python-wordcount-stage12-13 \
  -D mapreduce.job.reduces=1 \
  -files mapper.py,reducer.py \
  -mapper "python3 mapper.py" \
  -reducer "python3 reducer.py" \
  -input /user/hduser/python_wordcount/input \
  -output /user/hduser/python_wordcount/output
```

The mapper and reducer communicate through standard input/output. Hadoop Streaming performs the shuffle and sort between them.

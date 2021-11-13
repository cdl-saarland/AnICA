TODO write this

independent llvm bug:

https://bugs.llvm.org/show_bug.cgi?id=50725

original: 302 instructions

manually minimized: 3


> That is a pretty rare situation. In fact, I believe that it only affects a very few heavily microcoded instructions like FXRSTOR, from some specific Intel scheduling models.
> I am not surprised if this issue has never been found before, and you are only finding it now because you are testing FXRSTOR (which is heavily microcoded, and it has a really ugly resource consumption sequence associated with the write).
> More importantly, FXRSTOR `explicitly consumes` multiple partially overlapping resources in a same write. That is the problem.


Fixing commit:
https://github.com/llvm/llvm-project/commit/70b37f4c03cd189c94167dc22d9f5303c8773092

https://reviews.llvm.org/rG70b37f4c03cd189c94167dc22d9f5303c8773092


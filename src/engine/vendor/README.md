# Runtime timer dependency

`fake-timers.js` bundles [@sinonjs/fake-timers](https://github.com/sinonjs/fake-timers) 15.4.0, @sinonjs/commons 3.0.1 and type-detect 4.0.8 with esbuild 0.28.0. The unmodified upstream code and license notices are retained; full dependency licenses are in `fake-timers.LICENSE.txt`.

The runtime host injects this local bundle before game code and uses the public `install` and `tickAsync` APIs. Advancing time does not register additional browser initialization scripts. Exported games do not load it. End users need neither npm nor network access to obtain the bundle.

To rebuild from the source repo, run `uv run python src/engine/vendor/build.py`. Only this developer rebuild requires Node.js/npm. All build dependencies and npm cache stay in the project's `.cache/`. The browser build leaves Node's `util` external because upstream accesses it only when a Node process global exists; the bundle runs in a fresh browser page before game code.

var VibeGameTimers = (() => {
  var __getOwnPropNames = Object.getOwnPropertyNames;
  var __require = /* @__PURE__ */ ((x) => typeof require !== "undefined" ? require : typeof Proxy !== "undefined" ? new Proxy(x, {
    get: (a, b) => (typeof require !== "undefined" ? require : a)[b]
  }) : x)(function(x) {
    if (typeof require !== "undefined") return require.apply(this, arguments);
    throw Error('Dynamic require of "' + x + '" is not supported');
  });
  var __commonJS = (cb, mod) => function __require2() {
    return mod || (0, cb[__getOwnPropNames(cb)[0]])((mod = { exports: {} }).exports, mod), mod.exports;
  };

  // node_modules/@sinonjs/commons/lib/global.js
  var require_global = __commonJS({
    "node_modules/@sinonjs/commons/lib/global.js"(exports, module) {
      "use strict";
      var globalObject;
      if (typeof global !== "undefined") {
        globalObject = global;
      } else if (typeof window !== "undefined") {
        globalObject = window;
      } else {
        globalObject = self;
      }
      module.exports = globalObject;
    }
  });

  // node_modules/@sinonjs/commons/lib/prototypes/throws-on-proto.js
  var require_throws_on_proto = __commonJS({
    "node_modules/@sinonjs/commons/lib/prototypes/throws-on-proto.js"(exports, module) {
      "use strict";
      var throwsOnProto;
      try {
        const object = {};
        object.__proto__;
        throwsOnProto = false;
      } catch (_) {
        throwsOnProto = true;
      }
      module.exports = throwsOnProto;
    }
  });

  // node_modules/@sinonjs/commons/lib/prototypes/copy-prototype-methods.js
  var require_copy_prototype_methods = __commonJS({
    "node_modules/@sinonjs/commons/lib/prototypes/copy-prototype-methods.js"(exports, module) {
      "use strict";
      var call = Function.call;
      var throwsOnProto = require_throws_on_proto();
      var disallowedProperties = [
        // ignore size because it throws from Map
        "size",
        "caller",
        "callee",
        "arguments"
      ];
      if (throwsOnProto) {
        disallowedProperties.push("__proto__");
      }
      module.exports = function copyPrototypeMethods(prototype) {
        return Object.getOwnPropertyNames(prototype).reduce(
          function(result, name) {
            if (disallowedProperties.includes(name)) {
              return result;
            }
            if (typeof prototype[name] !== "function") {
              return result;
            }
            result[name] = call.bind(prototype[name]);
            return result;
          },
          /* @__PURE__ */ Object.create(null)
        );
      };
    }
  });

  // node_modules/@sinonjs/commons/lib/prototypes/array.js
  var require_array = __commonJS({
    "node_modules/@sinonjs/commons/lib/prototypes/array.js"(exports, module) {
      "use strict";
      var copyPrototype = require_copy_prototype_methods();
      module.exports = copyPrototype(Array.prototype);
    }
  });

  // node_modules/@sinonjs/commons/lib/called-in-order.js
  var require_called_in_order = __commonJS({
    "node_modules/@sinonjs/commons/lib/called-in-order.js"(exports, module) {
      "use strict";
      var every = require_array().every;
      function hasCallsLeft(callMap, spy) {
        if (callMap[spy.id] === void 0) {
          callMap[spy.id] = 0;
        }
        return callMap[spy.id] < spy.callCount;
      }
      function checkAdjacentCalls(callMap, spy, index, spies) {
        var calledBeforeNext = true;
        if (index !== spies.length - 1) {
          calledBeforeNext = spy.calledBefore(spies[index + 1]);
        }
        if (hasCallsLeft(callMap, spy) && calledBeforeNext) {
          callMap[spy.id] += 1;
          return true;
        }
        return false;
      }
      function calledInOrder(spies) {
        var callMap = {};
        var _spies = arguments.length > 1 ? arguments : spies;
        return every(_spies, checkAdjacentCalls.bind(null, callMap));
      }
      module.exports = calledInOrder;
    }
  });

  // node_modules/@sinonjs/commons/lib/class-name.js
  var require_class_name = __commonJS({
    "node_modules/@sinonjs/commons/lib/class-name.js"(exports, module) {
      "use strict";
      function className(value) {
        const name = value.constructor && value.constructor.name;
        return name || null;
      }
      module.exports = className;
    }
  });

  // node_modules/@sinonjs/commons/lib/deprecated.js
  var require_deprecated = __commonJS({
    "node_modules/@sinonjs/commons/lib/deprecated.js"(exports) {
      "use strict";
      exports.wrap = function(func, msg) {
        var wrapped = function() {
          exports.printWarning(msg);
          return func.apply(this, arguments);
        };
        if (func.prototype) {
          wrapped.prototype = func.prototype;
        }
        return wrapped;
      };
      exports.defaultMsg = function(packageName, funcName) {
        return `${packageName}.${funcName} is deprecated and will be removed from the public API in a future version of ${packageName}.`;
      };
      exports.printWarning = function(msg) {
        if (typeof process === "object" && process.emitWarning) {
          process.emitWarning(msg);
        } else if (console.info) {
          console.info(msg);
        } else {
          console.log(msg);
        }
      };
    }
  });

  // node_modules/@sinonjs/commons/lib/every.js
  var require_every = __commonJS({
    "node_modules/@sinonjs/commons/lib/every.js"(exports, module) {
      "use strict";
      module.exports = function every(obj, fn) {
        var pass = true;
        try {
          obj.forEach(function() {
            if (!fn.apply(this, arguments)) {
              throw new Error();
            }
          });
        } catch (e) {
          pass = false;
        }
        return pass;
      };
    }
  });

  // node_modules/@sinonjs/commons/lib/function-name.js
  var require_function_name = __commonJS({
    "node_modules/@sinonjs/commons/lib/function-name.js"(exports, module) {
      "use strict";
      module.exports = function functionName(func) {
        if (!func) {
          return "";
        }
        try {
          return func.displayName || func.name || // Use function decomposition as a last resort to get function
          // name. Does not rely on function decomposition to work - if it
          // doesn't debugging will be slightly less informative
          // (i.e. toString will say 'spy' rather than 'myFunc').
          (String(func).match(/function ([^\s(]+)/) || [])[1];
        } catch (e) {
          return "";
        }
      };
    }
  });

  // node_modules/@sinonjs/commons/lib/order-by-first-call.js
  var require_order_by_first_call = __commonJS({
    "node_modules/@sinonjs/commons/lib/order-by-first-call.js"(exports, module) {
      "use strict";
      var sort = require_array().sort;
      var slice = require_array().slice;
      function comparator(a, b) {
        var aCall = a.getCall(0);
        var bCall = b.getCall(0);
        var aId = aCall && aCall.callId || -1;
        var bId = bCall && bCall.callId || -1;
        return aId < bId ? -1 : 1;
      }
      function orderByFirstCall(spies) {
        return sort(slice(spies), comparator);
      }
      module.exports = orderByFirstCall;
    }
  });

  // node_modules/@sinonjs/commons/lib/prototypes/function.js
  var require_function = __commonJS({
    "node_modules/@sinonjs/commons/lib/prototypes/function.js"(exports, module) {
      "use strict";
      var copyPrototype = require_copy_prototype_methods();
      module.exports = copyPrototype(Function.prototype);
    }
  });

  // node_modules/@sinonjs/commons/lib/prototypes/map.js
  var require_map = __commonJS({
    "node_modules/@sinonjs/commons/lib/prototypes/map.js"(exports, module) {
      "use strict";
      var copyPrototype = require_copy_prototype_methods();
      module.exports = copyPrototype(Map.prototype);
    }
  });

  // node_modules/@sinonjs/commons/lib/prototypes/object.js
  var require_object = __commonJS({
    "node_modules/@sinonjs/commons/lib/prototypes/object.js"(exports, module) {
      "use strict";
      var copyPrototype = require_copy_prototype_methods();
      module.exports = copyPrototype(Object.prototype);
    }
  });

  // node_modules/@sinonjs/commons/lib/prototypes/set.js
  var require_set = __commonJS({
    "node_modules/@sinonjs/commons/lib/prototypes/set.js"(exports, module) {
      "use strict";
      var copyPrototype = require_copy_prototype_methods();
      module.exports = copyPrototype(Set.prototype);
    }
  });

  // node_modules/@sinonjs/commons/lib/prototypes/string.js
  var require_string = __commonJS({
    "node_modules/@sinonjs/commons/lib/prototypes/string.js"(exports, module) {
      "use strict";
      var copyPrototype = require_copy_prototype_methods();
      module.exports = copyPrototype(String.prototype);
    }
  });

  // node_modules/@sinonjs/commons/lib/prototypes/index.js
  var require_prototypes = __commonJS({
    "node_modules/@sinonjs/commons/lib/prototypes/index.js"(exports, module) {
      "use strict";
      module.exports = {
        array: require_array(),
        function: require_function(),
        map: require_map(),
        object: require_object(),
        set: require_set(),
        string: require_string()
      };
    }
  });

  // node_modules/type-detect/type-detect.js
  var require_type_detect = __commonJS({
    "node_modules/type-detect/type-detect.js"(exports, module) {
      (function(global2, factory) {
        typeof exports === "object" && typeof module !== "undefined" ? module.exports = factory() : typeof define === "function" && define.amd ? define(factory) : global2.typeDetect = factory();
      })(exports, (function() {
        "use strict";
        var promiseExists = typeof Promise === "function";
        var globalObject = typeof self === "object" ? self : global;
        var symbolExists = typeof Symbol !== "undefined";
        var mapExists = typeof Map !== "undefined";
        var setExists = typeof Set !== "undefined";
        var weakMapExists = typeof WeakMap !== "undefined";
        var weakSetExists = typeof WeakSet !== "undefined";
        var dataViewExists = typeof DataView !== "undefined";
        var symbolIteratorExists = symbolExists && typeof Symbol.iterator !== "undefined";
        var symbolToStringTagExists = symbolExists && typeof Symbol.toStringTag !== "undefined";
        var setEntriesExists = setExists && typeof Set.prototype.entries === "function";
        var mapEntriesExists = mapExists && typeof Map.prototype.entries === "function";
        var setIteratorPrototype = setEntriesExists && Object.getPrototypeOf((/* @__PURE__ */ new Set()).entries());
        var mapIteratorPrototype = mapEntriesExists && Object.getPrototypeOf((/* @__PURE__ */ new Map()).entries());
        var arrayIteratorExists = symbolIteratorExists && typeof Array.prototype[Symbol.iterator] === "function";
        var arrayIteratorPrototype = arrayIteratorExists && Object.getPrototypeOf([][Symbol.iterator]());
        var stringIteratorExists = symbolIteratorExists && typeof String.prototype[Symbol.iterator] === "function";
        var stringIteratorPrototype = stringIteratorExists && Object.getPrototypeOf(""[Symbol.iterator]());
        var toStringLeftSliceLength = 8;
        var toStringRightSliceLength = -1;
        function typeDetect(obj) {
          var typeofObj = typeof obj;
          if (typeofObj !== "object") {
            return typeofObj;
          }
          if (obj === null) {
            return "null";
          }
          if (obj === globalObject) {
            return "global";
          }
          if (Array.isArray(obj) && (symbolToStringTagExists === false || !(Symbol.toStringTag in obj))) {
            return "Array";
          }
          if (typeof window === "object" && window !== null) {
            if (typeof window.location === "object" && obj === window.location) {
              return "Location";
            }
            if (typeof window.document === "object" && obj === window.document) {
              return "Document";
            }
            if (typeof window.navigator === "object") {
              if (typeof window.navigator.mimeTypes === "object" && obj === window.navigator.mimeTypes) {
                return "MimeTypeArray";
              }
              if (typeof window.navigator.plugins === "object" && obj === window.navigator.plugins) {
                return "PluginArray";
              }
            }
            if ((typeof window.HTMLElement === "function" || typeof window.HTMLElement === "object") && obj instanceof window.HTMLElement) {
              if (obj.tagName === "BLOCKQUOTE") {
                return "HTMLQuoteElement";
              }
              if (obj.tagName === "TD") {
                return "HTMLTableDataCellElement";
              }
              if (obj.tagName === "TH") {
                return "HTMLTableHeaderCellElement";
              }
            }
          }
          var stringTag = symbolToStringTagExists && obj[Symbol.toStringTag];
          if (typeof stringTag === "string") {
            return stringTag;
          }
          var objPrototype = Object.getPrototypeOf(obj);
          if (objPrototype === RegExp.prototype) {
            return "RegExp";
          }
          if (objPrototype === Date.prototype) {
            return "Date";
          }
          if (promiseExists && objPrototype === Promise.prototype) {
            return "Promise";
          }
          if (setExists && objPrototype === Set.prototype) {
            return "Set";
          }
          if (mapExists && objPrototype === Map.prototype) {
            return "Map";
          }
          if (weakSetExists && objPrototype === WeakSet.prototype) {
            return "WeakSet";
          }
          if (weakMapExists && objPrototype === WeakMap.prototype) {
            return "WeakMap";
          }
          if (dataViewExists && objPrototype === DataView.prototype) {
            return "DataView";
          }
          if (mapExists && objPrototype === mapIteratorPrototype) {
            return "Map Iterator";
          }
          if (setExists && objPrototype === setIteratorPrototype) {
            return "Set Iterator";
          }
          if (arrayIteratorExists && objPrototype === arrayIteratorPrototype) {
            return "Array Iterator";
          }
          if (stringIteratorExists && objPrototype === stringIteratorPrototype) {
            return "String Iterator";
          }
          if (objPrototype === null) {
            return "Object";
          }
          return Object.prototype.toString.call(obj).slice(toStringLeftSliceLength, toStringRightSliceLength);
        }
        return typeDetect;
      }));
    }
  });

  // node_modules/@sinonjs/commons/lib/type-of.js
  var require_type_of = __commonJS({
    "node_modules/@sinonjs/commons/lib/type-of.js"(exports, module) {
      "use strict";
      var type = require_type_detect();
      module.exports = function typeOf(value) {
        return type(value).toLowerCase();
      };
    }
  });

  // node_modules/@sinonjs/commons/lib/value-to-string.js
  var require_value_to_string = __commonJS({
    "node_modules/@sinonjs/commons/lib/value-to-string.js"(exports, module) {
      "use strict";
      function valueToString(value) {
        if (value && value.toString) {
          return value.toString();
        }
        return String(value);
      }
      module.exports = valueToString;
    }
  });

  // node_modules/@sinonjs/commons/lib/index.js
  var require_lib = __commonJS({
    "node_modules/@sinonjs/commons/lib/index.js"(exports, module) {
      "use strict";
      module.exports = {
        global: require_global(),
        calledInOrder: require_called_in_order(),
        className: require_class_name(),
        deprecated: require_deprecated(),
        every: require_every(),
        functionName: require_function_name(),
        orderByFirstCall: require_order_by_first_call(),
        prototypes: require_prototypes(),
        typeOf: require_type_of(),
        valueToString: require_value_to_string()
      };
    }
  });

  // (disabled):timers
  var require_timers = __commonJS({
    "(disabled):timers"() {
    }
  });

  // (disabled):timers/promises
  var require_promises = __commonJS({
    "(disabled):timers/promises"() {
    }
  });

  // node_modules/@sinonjs/fake-timers/src/fake-timers-src.js
  var require_fake_timers_src = __commonJS({
    "node_modules/@sinonjs/fake-timers/src/fake-timers-src.js"(exports, module) {
      "use strict";
      var globalObject = require_lib().global;
      var timersModule;
      var timersPromisesModule;
      if (typeof __require === "function" && typeof module === "object") {
        try {
          timersModule = require_timers();
        } catch {
        }
        try {
          timersPromisesModule = require_promises();
        } catch {
        }
      }
      function withGlobal(_global) {
        const maxTimeout = Math.pow(2, 31) - 1;
        const idCounterStart = 1e12;
        const NOOP = function() {
          return void 0;
        };
        const NOOP_ARRAY = function() {
          return [];
        };
        const isPresent = {};
        let timeoutResult, addTimerReturnsObject = false;
        if (_global.setTimeout) {
          isPresent.setTimeout = true;
          timeoutResult = _global.setTimeout(NOOP, 0);
          addTimerReturnsObject = typeof timeoutResult === "object";
        }
        isPresent.clearTimeout = Boolean(_global.clearTimeout);
        isPresent.setInterval = Boolean(_global.setInterval);
        isPresent.clearInterval = Boolean(_global.clearInterval);
        isPresent.hrtime = _global.process && typeof _global.process.hrtime === "function";
        isPresent.hrtimeBigint = isPresent.hrtime && typeof _global.process.hrtime.bigint === "function";
        isPresent.nextTick = _global.process && typeof _global.process.nextTick === "function";
        const utilPromisify = _global.process && __require("util").promisify;
        isPresent.performance = _global.performance && typeof _global.performance.now === "function";
        const hasPerformancePrototype = _global.Performance && (typeof _global.Performance).match(/^(function|object)$/);
        const hasPerformanceConstructorPrototype = _global.performance && _global.performance.constructor && _global.performance.constructor.prototype;
        isPresent.queueMicrotask = Object.prototype.hasOwnProperty.call(
          _global,
          "queueMicrotask"
        );
        isPresent.requestAnimationFrame = _global.requestAnimationFrame && typeof _global.requestAnimationFrame === "function";
        isPresent.cancelAnimationFrame = _global.cancelAnimationFrame && typeof _global.cancelAnimationFrame === "function";
        isPresent.requestIdleCallback = _global.requestIdleCallback && typeof _global.requestIdleCallback === "function";
        isPresent.cancelIdleCallback = _global.cancelIdleCallback && typeof _global.cancelIdleCallback === "function";
        isPresent.setImmediate = _global.setImmediate && typeof _global.setImmediate === "function";
        isPresent.clearImmediate = _global.clearImmediate && typeof _global.clearImmediate === "function";
        isPresent.Intl = _global.Intl && typeof _global.Intl === "object";
        isPresent.Temporal = _global.Temporal !== null && typeof _global.Temporal === "object" && typeof _global.Temporal.Now !== "undefined" && typeof _global.Temporal.Instant !== "undefined";
        if (_global.clearTimeout) {
          _global.clearTimeout(timeoutResult);
        }
        const NativeDate = _global.Date;
        const NativeIntl = isPresent.Intl ? Object.defineProperties(
          /* @__PURE__ */ Object.create(null),
          Object.getOwnPropertyDescriptors(_global.Intl)
        ) : void 0;
        const NativeTemporal = isPresent.Temporal ? _global.Temporal : void 0;
        let uniqueTimerId = idCounterStart;
        let uniqueTimerOrder = 0;
        if (NativeDate === void 0) {
          throw new Error(
            "The global scope doesn't have a `Date` object (see https://github.com/sinonjs/sinon/issues/1852#issuecomment-419622780)"
          );
        }
        isPresent.Date = true;
        class FakePerformanceEntry {
          constructor(name, entryType, startTime, duration) {
            this.name = name;
            this.entryType = entryType;
            this.startTime = startTime;
            this.duration = duration;
          }
          toJSON() {
            return JSON.stringify({ ...this });
          }
        }
        function isNumberFinite(num) {
          if (Number.isFinite) {
            return Number.isFinite(num);
          }
          return isFinite(num);
        }
        function checkIsNearInfiniteLimit(clock, i) {
          if (clock.loopLimit && i === clock.loopLimit - 1) {
            clock.isNearInfiniteLimit = true;
          }
        }
        function resetIsNearInfiniteLimit(clock) {
          if (clock) {
            clock.isNearInfiniteLimit = false;
          }
        }
        function parseTime(str) {
          if (!str) {
            return 0;
          }
          const strings = str.split(":");
          const l = strings.length;
          let i = l;
          let ms = 0;
          let parsed;
          if (l > 3 || !/^(\d\d:){0,2}\d\d?$/.test(str)) {
            throw new Error(
              "tick only understands numbers, 'm:s' and 'h:m:s'. Each part must be two digits"
            );
          }
          while (i--) {
            parsed = parseInt(strings[i], 10);
            if (parsed >= 60) {
              throw new Error(`Invalid time ${str}`);
            }
            ms += parsed * Math.pow(60, l - i - 1);
          }
          return ms * 1e3;
        }
        function nanoRemainder(msFloat) {
          const modulo = 1e6;
          const remainder = msFloat * 1e6 % modulo;
          const positiveRemainder = remainder < 0 ? remainder + modulo : remainder;
          return Math.floor(positiveRemainder);
        }
        function getEpoch(epoch) {
          if (!epoch) {
            return 0;
          }
          if (typeof epoch === "number") {
            return epoch;
          }
          if (typeof /** @type {Date} */
          epoch.getTime === "function") {
            return (
              /** @type {Date} */
              epoch.getTime()
            );
          }
          if (typeof /** @type {TemporalTimelike} */
          epoch.epochMilliseconds === "number") {
            return (
              /** @type {TemporalTimelike} */
              epoch.epochMilliseconds
            );
          }
          throw new TypeError("now should be milliseconds since UNIX epoch");
        }
        function inRange(from, to, timer) {
          return timer && timer.callAt >= from && timer.callAt <= to;
        }
        function getInfiniteLoopError(clock, job) {
          const infiniteLoopError = new Error(
            `Aborting after running ${clock.loopLimit} timers, assuming an infinite loop!`
          );
          if (!job.error) {
            return infiniteLoopError;
          }
          const computedTargetPattern = /target\.*[<|(|[].*?[>|\]|)]\s*/;
          let clockMethodPattern = new RegExp(
            String(Object.keys(clock).join("|"))
          );
          if (addTimerReturnsObject) {
            clockMethodPattern = new RegExp(
              `\\s+at (Object\\.)?(?:${Object.keys(clock).join("|")})\\s+`
            );
          }
          let matchedLineIndex = -1;
          job.error.stack.split("\n").some(function(line, i) {
            const matchedComputedTarget = line.match(computedTargetPattern);
            if (matchedComputedTarget) {
              matchedLineIndex = i;
              return true;
            }
            const matchedClockMethod = line.match(clockMethodPattern);
            if (matchedClockMethod) {
              matchedLineIndex = i;
              return false;
            }
            return matchedLineIndex >= 0;
          });
          const stack = `${infiniteLoopError}
${job.type || "Microtask"} - ${job.func.name || "anonymous"}
${job.error.stack.split("\n").slice(matchedLineIndex + 1).join("\n")}`;
          try {
            Object.defineProperty(infiniteLoopError, "stack", {
              value: stack
            });
          } catch {
          }
          return infiniteLoopError;
        }
        function createDate() {
          class ClockDate extends NativeDate {
            /** @type {Clock} */
            static clock;
            constructor(...args) {
              if (args.length === 0) {
                super(ClockDate.clock.now);
              } else {
                super(...args);
              }
              Object.defineProperty(this, "constructor", {
                value: NativeDate,
                enumerable: false
              });
            }
            static [Symbol.hasInstance](instance) {
              return instance instanceof NativeDate;
            }
          }
          ClockDate.isFake = true;
          if (NativeDate.now) {
            ClockDate.now = function now() {
              return ClockDate.clock.now;
            };
          }
          const NativeDateWithToSource = (
            /** @type {typeof Date & { toSource?: () => string }} */
            NativeDate
          );
          if (NativeDateWithToSource.toSource) {
            ClockDate.toSource = function toSource() {
              return NativeDateWithToSource.toSource();
            };
          }
          ClockDate.toString = function toString() {
            return NativeDateWithToSource.toString();
          };
          const ClockDateProxy = new Proxy(ClockDate, {
            // handler for [[Call]] invocations (i.e. not using `new`)
            apply() {
              if (this instanceof ClockDate) {
                throw new TypeError(
                  "A Proxy should only capture `new` calls with the `construct` handler. This is not supposed to be possible, so check the logic."
                );
              }
              return new NativeDate(ClockDate.clock.now).toString();
            }
          });
          return (
            /** @type {typeof Date & { clock: Clock }} */
            /** @type {unknown} */
            ClockDateProxy
          );
        }
        function createIntl(clock) {
          const IntlWithClock = { clock };
          Object.getOwnPropertyNames(NativeIntl).forEach(
            (property) => IntlWithClock[property] = NativeIntl[property]
          );
          IntlWithClock.DateTimeFormat = function(...args) {
            const realFormatter = new NativeIntl.DateTimeFormat(...args);
            const formatter = {};
            ["formatRange", "formatRangeToParts", "resolvedOptions"].forEach(
              (method) => {
                formatter[method] = realFormatter[method].bind(realFormatter);
              }
            );
            ["format", "formatToParts"].forEach((method) => {
              formatter[method] = function(date) {
                return realFormatter[method](
                  date || IntlWithClock.clock.now
                );
              };
            });
            return formatter;
          };
          IntlWithClock.DateTimeFormat.prototype = Object.create(
            NativeIntl.DateTimeFormat.prototype
          );
          IntlWithClock.DateTimeFormat.supportedLocalesOf = NativeIntl.DateTimeFormat.supportedLocalesOf;
          return IntlWithClock;
        }
        function createTemporal(clock, getNanos) {
          const fakeNow = {
            instant() {
              return NativeTemporal.Instant.fromEpochNanoseconds(
                BigInt(clock.now) * 1000000n + BigInt(getNanos())
              );
            },
            timeZoneId() {
              return NativeTemporal.Now.timeZoneId();
            },
            zonedDateTimeISO(timeZone) {
              const tz = timeZone ?? NativeTemporal.Now.timeZoneId();
              return fakeNow.instant().toZonedDateTimeISO(tz);
            },
            plainDateTimeISO(timeZone) {
              return fakeNow.zonedDateTimeISO(timeZone).toPlainDateTime();
            },
            plainDateISO(timeZone) {
              return fakeNow.zonedDateTimeISO(timeZone).toPlainDate();
            },
            plainTimeISO(timeZone) {
              return fakeNow.zonedDateTimeISO(timeZone).toPlainTime();
            }
          };
          const TemporalWithClock = Object.create(
            Object.getPrototypeOf(NativeTemporal)
          );
          [
            ...Object.getOwnPropertyNames(NativeTemporal),
            ...Object.getOwnPropertySymbols(NativeTemporal)
          ].forEach((prop) => {
            Object.defineProperty(
              TemporalWithClock,
              prop,
              Object.getOwnPropertyDescriptor(NativeTemporal, prop)
            );
          });
          Object.defineProperty(TemporalWithClock, "Now", {
            value: fakeNow,
            writable: true,
            enumerable: false,
            configurable: true
          });
          return TemporalWithClock;
        }
        function enqueueJob(clock, job) {
          if (!clock.jobs) {
            clock.jobs = [];
          }
          clock.jobs.push(job);
        }
        function runJobs(clock) {
          if (!clock.jobs) {
            return;
          }
          const wasNearLimit = clock.isNearInfiniteLimit;
          for (let i = 0; i < clock.jobs.length; i++) {
            const job = clock.jobs[i];
            job.func.apply(null, job.args);
            checkIsNearInfiniteLimit(clock, i);
            if (clock.loopLimit && i > clock.loopLimit) {
              throw getInfiniteLoopError(clock, job);
            }
          }
          if (!wasNearLimit) {
            resetIsNearInfiniteLimit(clock);
          }
          clock.jobs = [];
        }
        class TimerHeap {
          constructor() {
            this.timers = [];
          }
          /**
           * Look at the next timer without removing it.
           * This is the timer the clock would run first if time advanced now.
           * @returns {Timer}
           */
          peek() {
            return this.timers[0];
          }
          /**
           * Add a timer to the waiting room, then move it upward until it is in
           * the right place relative to the timers it should run before and after.
           * @param {Timer} timer
           */
          push(timer) {
            this.timers.push(timer);
            this.bubbleUp(this.timers.length - 1);
          }
          /**
           * Remove and return the next timer to run.
           *
           * We pull the front timer out, move the last timer into the empty spot,
           * and then shift that replacement down until the ordering is correct
           * again. That avoids rebuilding the whole list from scratch.
           * @returns {Timer|undefined}
           */
          pop() {
            if (this.timers.length === 0) {
              return void 0;
            }
            const first = this.timers[0];
            const last = this.timers.pop();
            if (this.timers.length > 0) {
              this.timers[0] = last;
              last.heapIndex = 0;
              this.bubbleDown(0);
            }
            delete first.heapIndex;
            return first;
          }
          /**
           * Remove a specific timer from the waiting room.
           *
           * The heap stores timers in a shape that lets us jump directly to the
           * timer's current position, replace it with the last timer, and then
           * move that replacement up or down until the ordering is correct again.
           * @param {Timer} timer
           * @returns {boolean}
           */
          remove(timer) {
            const index = timer.heapIndex;
            if (index === void 0 || this.timers[index] !== timer) {
              return false;
            }
            const last = this.timers.pop();
            if (timer !== last) {
              this.timers[index] = last;
              last.heapIndex = index;
              if (compareTimers(last, timer) < 0) {
                this.bubbleUp(index);
              } else {
                this.bubbleDown(index);
              }
            }
            delete timer.heapIndex;
            return true;
          }
          /**
           * Move a timer toward the front until it is no longer "earlier" than
           * the timer above it.
           *
           * Conceptually, this is what happens when something newly scheduled
           * turns out to belong ahead of its parent in the waiting room. We keep
           * swapping it upward until it is no longer out of place.
           * @param {number} index
           */
          bubbleUp(index) {
            const timer = this.timers[index];
            let currentIndex = index;
            while (currentIndex > 0) {
              const parentIndex = Math.floor((currentIndex - 1) / 2);
              const parent = this.timers[parentIndex];
              if (compareTimers(timer, parent) < 0) {
                this.timers[currentIndex] = parent;
                parent.heapIndex = currentIndex;
                currentIndex = parentIndex;
              } else {
                break;
              }
            }
            this.timers[currentIndex] = timer;
            timer.heapIndex = currentIndex;
          }
          /**
           * Move a timer away from the front until the timer below it is no
           * longer supposed to run after it.
           *
           * This is the opposite of `bubbleUp`: when a timer at the front is
           * removed or moved, the replacement may be too far ahead, so we
           * repeatedly swap it downward with the best child until the waiting
           * room is ordered again.
           * @param {number} index
           */
          bubbleDown(index) {
            const timer = this.timers[index];
            let currentIndex = index;
            const halfLength = Math.floor(this.timers.length / 2);
            while (currentIndex < halfLength) {
              const leftIndex = currentIndex * 2 + 1;
              const rightIndex = leftIndex + 1;
              let bestChildIndex = leftIndex;
              let bestChild = this.timers[leftIndex];
              if (rightIndex < this.timers.length && compareTimers(this.timers[rightIndex], bestChild) < 0) {
                bestChildIndex = rightIndex;
                bestChild = this.timers[rightIndex];
              }
              if (compareTimers(bestChild, timer) < 0) {
                this.timers[currentIndex] = bestChild;
                bestChild.heapIndex = currentIndex;
                currentIndex = bestChildIndex;
              } else {
                break;
              }
            }
            this.timers[currentIndex] = timer;
            timer.heapIndex = currentIndex;
          }
        }
        function ensureTimerState(clock) {
          if (!clock.timers) {
            clock.timers = /* @__PURE__ */ new Map();
            clock.timerHeap = new TimerHeap();
          }
        }
        function hasTimer(clock, id) {
          return clock.timers ? clock.timers.has(id) : false;
        }
        function getTimer(clock, id) {
          return clock.timers ? clock.timers.get(id) : void 0;
        }
        function setTimer(clock, timer) {
          ensureTimerState(clock);
          clock.timers.set(timer.id, timer);
        }
        function deleteTimer(clock, id) {
          return clock.timers ? clock.timers.delete(id) : false;
        }
        function forEachActiveTimer(clock, callback) {
          if (!clock.timers) {
            return;
          }
          for (const timer of clock.timers.values()) {
            callback(timer);
          }
        }
        function rebuildTimerHeap(clock) {
          clock.timerHeap = new TimerHeap();
          forEachActiveTimer(clock, (timer) => {
            clock.timerHeap.push(timer);
          });
        }
        function addTimer(clock, timer) {
          if (timer.func === void 0) {
            throw new Error("Callback must be provided to timer calls");
          }
          if (typeof timer.func !== "function") {
            throw new TypeError(
              `[ERR_INVALID_CALLBACK]: Callback must be a function. Received ${timer.func} of type ${typeof timer.func}`
            );
          }
          if (clock.isNearInfiniteLimit) {
            timer.error = new Error();
          }
          timer.type = timer.immediate ? "Immediate" : "Timeout";
          if (Object.prototype.hasOwnProperty.call(timer, "delay")) {
            if (typeof timer.delay !== "number") {
              timer.delay = parseInt(timer.delay, 10);
            }
            if (!isNumberFinite(timer.delay)) {
              timer.delay = 0;
            }
            timer.delay = timer.delay > maxTimeout ? 1 : timer.delay;
            timer.delay = Math.max(0, timer.delay);
          }
          if (Object.prototype.hasOwnProperty.call(timer, "interval")) {
            timer.type = "Interval";
            timer.interval = timer.interval > maxTimeout ? 1 : timer.interval;
          }
          if (Object.prototype.hasOwnProperty.call(timer, "animation")) {
            timer.type = "AnimationFrame";
            timer.animation = true;
          }
          if (Object.prototype.hasOwnProperty.call(timer, "requestIdleCallback")) {
            if (!timer.delay) {
              timer.type = "IdleCallback";
            }
            timer.requestIdleCallback = true;
          }
          ensureTimerState(clock);
          while (hasTimer(clock, uniqueTimerId)) {
            uniqueTimerId++;
            if (uniqueTimerId >= Number.MAX_SAFE_INTEGER) {
              uniqueTimerId = idCounterStart;
            }
          }
          timer.id = uniqueTimerId++;
          if (uniqueTimerId >= Number.MAX_SAFE_INTEGER) {
            uniqueTimerId = idCounterStart;
          }
          timer.order = uniqueTimerOrder++;
          timer.createdAt = clock.now;
          timer.callAt = clock.now + (parseInt(String(timer.delay)) || (clock.duringTick ? 1 : 0));
          setTimer(clock, timer);
          clock.timerHeap.push(timer);
          if (addTimerReturnsObject) {
            const res = {
              refed: true,
              ref: function() {
                this.refed = true;
                return this;
              },
              unref: function() {
                this.refed = false;
                return this;
              },
              hasRef: function() {
                return this.refed;
              },
              refresh: function() {
                timer.callAt = clock.now + (parseInt(String(timer.delay)) || (clock.duringTick ? 1 : 0));
                clock.timerHeap.remove(timer);
                timer.order = uniqueTimerOrder++;
                setTimer(clock, timer);
                clock.timerHeap.push(timer);
                return this;
              },
              [Symbol.toPrimitive]: function() {
                return timer.id;
              }
            };
            return res;
          }
          return timer.id;
        }
        function compareTimers(a, b) {
          if (a.type === "IdleCallback" && b.type !== "IdleCallback") {
            return 1;
          }
          if (a.type !== "IdleCallback" && b.type === "IdleCallback") {
            return -1;
          }
          if (a.callAt < b.callAt) {
            return -1;
          }
          if (a.callAt > b.callAt) {
            return 1;
          }
          if (a.immediate && !b.immediate) {
            return -1;
          }
          if (!a.immediate && b.immediate) {
            return 1;
          }
          if (a.order < b.order) {
            return -1;
          }
          if (a.order > b.order) {
            return 1;
          }
          if (a.createdAt < b.createdAt) {
            return -1;
          }
          if (a.createdAt > b.createdAt) {
            return 1;
          }
          if (a.id < b.id) {
            return -1;
          }
          if (a.id > b.id) {
            return 1;
          }
          return 0;
        }
        function firstTimerInRange(clock, from, to) {
          if (!clock.timerHeap) {
            return null;
          }
          const timers2 = clock.timerHeap.timers;
          if (timers2.length === 1 && timers2[0].requestIdleCallback) {
            return timers2[0];
          }
          const first = clock.timerHeap.peek();
          if (first && inRange(from, to, first)) {
            return first;
          }
          let timer = null;
          for (let i = 0; i < timers2.length; i++) {
            if (inRange(from, to, timers2[i]) && (!timer || compareTimers(timer, timers2[i]) === 1)) {
              timer = timers2[i];
            }
          }
          return timer;
        }
        function firstTimer(clock) {
          if (!clock.timerHeap) {
            return null;
          }
          return clock.timerHeap.peek() || null;
        }
        function lastTimer(clock) {
          if (!clock.timerHeap) {
            return null;
          }
          const timers2 = clock.timerHeap.timers;
          let timer = null;
          for (let i = 0; i < timers2.length; i++) {
            if (!timer || compareTimers(timer, timers2[i]) === -1) {
              timer = timers2[i];
            }
          }
          return timer;
        }
        function callTimer(clock, timer) {
          if (typeof timer.interval === "number") {
            clock.timerHeap.remove(timer);
            timer.callAt += timer.interval;
            timer.order = uniqueTimerOrder++;
            if (clock.isNearInfiniteLimit) {
              timer.error = new Error();
            }
            clock.timerHeap.push(timer);
          } else {
            deleteTimer(clock, timer.id);
            clock.timerHeap.remove(timer);
          }
          if (typeof timer.func === "function") {
            timer.func.apply(null, timer.args);
          }
        }
        function getClearHandler(ttype) {
          if (ttype === "IdleCallback" || ttype === "AnimationFrame") {
            return `cancel${ttype}`;
          }
          return `clear${ttype}`;
        }
        function getScheduleHandler(ttype) {
          if (ttype === "IdleCallback" || ttype === "AnimationFrame") {
            return `request${ttype}`;
          }
          return `set${ttype}`;
        }
        function createWarnOnce() {
          let calls = 0;
          return function(msg) {
            !calls++ && console.warn(msg);
          };
        }
        const warnOnce = createWarnOnce();
        function clearTimer(clock, timerId, ttype) {
          if (!timerId) {
            return;
          }
          const id = Number(timerId);
          if (Number.isNaN(id) || id < idCounterStart) {
            const handlerName = getClearHandler(ttype);
            if (clock.shouldClearNativeTimers === true) {
              const nativeHandler = clock[`_${handlerName}`];
              return typeof nativeHandler === "function" ? nativeHandler(timerId) : void 0;
            }
            const stackTrace = new Error().stack.split("\n").slice(1).join("\n");
            warnOnce(
              `FakeTimers: ${handlerName} was invoked to clear a native timer instead of one created by this library.
To automatically clean-up native timers, use \`shouldClearNativeTimers\`.
${stackTrace}`
            );
          }
          if (hasTimer(clock, id)) {
            const timer = getTimer(clock, id);
            if (timer.type === ttype || timer.type === "Timeout" && ttype === "Interval" || timer.type === "Interval" && ttype === "Timeout") {
              deleteTimer(clock, id);
              clock.timerHeap.remove(timer);
            } else {
              const clear = getClearHandler(ttype);
              const schedule = getScheduleHandler(timer.type);
              throw new Error(
                `Cannot clear timer: timer created with ${schedule}() but cleared with ${clear}()`
              );
            }
          }
        }
        function hijackMethod(target, method, clock) {
          clock[method].hasOwnProperty = Object.prototype.hasOwnProperty.call(
            target,
            method
          );
          clock[`_${method}`] = target[method];
          if (method === "Date") {
            target[method] = clock[method];
          } else if (method === "Intl") {
            target[method] = clock[method];
          } else if (method === "Temporal") {
            target[method] = clock[method];
          } else if (method === "performance") {
            const originalPerfDescriptor = Object.getOwnPropertyDescriptor(
              target,
              method
            );
            if (originalPerfDescriptor && originalPerfDescriptor.get && !originalPerfDescriptor.set) {
              Object.defineProperty(
                clock,
                `_${method}`,
                originalPerfDescriptor
              );
              const perfDescriptor = Object.getOwnPropertyDescriptor(
                clock,
                method
              );
              Object.defineProperty(target, method, perfDescriptor);
            } else {
              target[method] = clock[method];
            }
          } else {
            target[method] = function() {
              return clock[method].apply(clock, arguments);
            };
            Object.defineProperties(
              target[method],
              Object.getOwnPropertyDescriptors(clock[method])
            );
          }
          target[method].clock = clock;
        }
        function doIntervalTick(clock, advanceTimeDelta) {
          clock.tick(advanceTimeDelta);
        }
        const timers = {
          setTimeout: _global.setTimeout,
          clearTimeout: _global.clearTimeout,
          setInterval: _global.setInterval,
          clearInterval: _global.clearInterval,
          Date: _global.Date
        };
        if (isPresent.setImmediate) {
          timers.setImmediate = _global.setImmediate;
        }
        if (isPresent.clearImmediate) {
          timers.clearImmediate = _global.clearImmediate;
        }
        if (isPresent.hrtime) {
          timers.hrtime = _global.process.hrtime;
        }
        if (isPresent.nextTick) {
          timers.nextTick = _global.process.nextTick;
        }
        if (isPresent.performance) {
          timers.performance = _global.performance;
        }
        if (isPresent.requestAnimationFrame) {
          timers.requestAnimationFrame = _global.requestAnimationFrame;
        }
        if (isPresent.queueMicrotask) {
          timers.queueMicrotask = _global.queueMicrotask;
        }
        if (isPresent.cancelAnimationFrame) {
          timers.cancelAnimationFrame = _global.cancelAnimationFrame;
        }
        if (isPresent.requestIdleCallback) {
          timers.requestIdleCallback = _global.requestIdleCallback;
        }
        if (isPresent.cancelIdleCallback) {
          timers.cancelIdleCallback = _global.cancelIdleCallback;
        }
        if (isPresent.Intl) {
          timers.Intl = NativeIntl;
        }
        if (isPresent.Temporal) {
          timers.Temporal = NativeTemporal;
        }
        const originalSetTimeout = _global.setImmediate || _global.setTimeout;
        const originalClearInterval = _global.clearInterval;
        const originalSetInterval = _global.setInterval;
        function createClock(start, loopLimit) {
          start = Math.floor(getEpoch(start));
          const startTimestamp = start;
          loopLimit = loopLimit || 1e3;
          let nanos = 0;
          let uninstalled = false;
          const adjustedSystemTime = [0, 0];
          const clock = (
            /** @type {Clock} */
            {
              now: start,
              Date: createDate(),
              loopLimit,
              isNearInfiniteLimit: false,
              tickMode: { mode: "manual", counter: 0, delta: void 0 }
            }
          );
          clock.Date.clock = clock;
          function getTimeToNextFrame() {
            return 16 - (clock.now - startTimestamp) % 16;
          }
          function hrtime(prev) {
            const millisSinceStart = clock.now - adjustedSystemTime[0] - startTimestamp;
            const secsSinceStart = Math.floor(millisSinceStart / 1e3);
            const remainderInNanos = (millisSinceStart - secsSinceStart * 1e3) * 1e6 + nanos - adjustedSystemTime[1];
            if (Array.isArray(prev)) {
              if (prev[1] > 1e9) {
                throw new TypeError(
                  "Number of nanoseconds can't exceed a billion"
                );
              }
              const oldSecs = prev[0];
              let nanoDiff = remainderInNanos - prev[1];
              let secDiff = secsSinceStart - oldSecs;
              if (nanoDiff < 0) {
                nanoDiff += 1e9;
                secDiff -= 1;
              }
              return [secDiff, nanoDiff];
            }
            return [secsSinceStart, remainderInNanos];
          }
          function fakePerformanceNow() {
            const hrt = hrtime();
            const millis = hrt[0] * 1e3 + hrt[1] / 1e6;
            return millis;
          }
          if (isPresent.hrtimeBigint) {
            hrtime.bigint = function() {
              const parts = hrtime();
              return BigInt(parts[0]) * BigInt(1e9) + BigInt(parts[1]);
            };
          }
          if (isPresent.Intl) {
            clock.Intl = createIntl(clock);
            clock.Intl.clock = clock;
          }
          if (isPresent.Temporal) {
            clock.Temporal = createTemporal(clock, () => nanos);
          }
          clock.setTickMode = function(tickModeConfig) {
            const { mode: newMode, delta: newDelta } = (
              /** @type {SetTickModeConfig} */
              tickModeConfig
            );
            const { mode: oldMode, delta: oldDelta } = clock.tickMode;
            if (newMode === oldMode && newDelta === oldDelta) {
              return;
            }
            if (oldMode === "interval") {
              originalClearInterval(clock.attachedInterval);
            }
            clock.tickMode = {
              counter: clock.tickMode.counter + 1,
              mode: newMode,
              delta: newDelta
            };
            if (newMode === "nextAsync") {
              advanceUntilModeChanges();
            } else if (newMode === "interval") {
              createIntervalTick(clock, newDelta || 20);
            }
          };
          async function advanceUntilModeChanges() {
            async function newMacrotask() {
              const channel = new MessageChannel();
              await new Promise((resolve) => {
                channel.port1.onmessage = () => {
                  resolve(void 0);
                  channel.port1.close();
                };
                channel.port2.postMessage(void 0);
              });
              channel.port1.close();
              channel.port2.close();
              await new Promise((resolve) => {
                originalSetTimeout(resolve);
              });
            }
            const { counter } = clock.tickMode;
            while (clock.tickMode.counter === counter) {
              await newMacrotask();
              if (clock.tickMode.counter !== counter) {
                return;
              }
              clock.next();
            }
          }
          function pauseAutoTickUntilFinished(promise) {
            if (clock.tickMode.mode !== "nextAsync") {
              return promise;
            }
            clock.setTickMode({ mode: "manual" });
            return promise.finally(() => {
              if (!uninstalled) {
                clock.setTickMode({ mode: "nextAsync" });
              }
            });
          }
          function getTimeToNextIdlePeriod() {
            let timeToNextIdlePeriod = 0;
            if (clock.countTimers() > 0) {
              timeToNextIdlePeriod = 50;
            }
            return timeToNextIdlePeriod;
          }
          clock.requestIdleCallback = function requestIdleCallback(func, { timeout } = (
            /** @type {{ timeout?: number }} */
            {}
          )) {
            const idleDeadline = {
              didTimeout: true,
              timeRemaining: getTimeToNextIdlePeriod
            };
            const result = addTimer(clock, {
              func,
              args: [idleDeadline],
              delay: timeout,
              requestIdleCallback: true
            });
            return Number(result);
          };
          clock.cancelIdleCallback = function cancelIdleCallback(timerId) {
            return clearTimer(clock, timerId, "IdleCallback");
          };
          clock.setTimeout = function setTimeout(func, timeout) {
            return addTimer(clock, {
              func,
              args: Array.prototype.slice.call(arguments, 2),
              delay: timeout
            });
          };
          if (typeof _global.Promise !== "undefined" && utilPromisify) {
            clock.setTimeout[utilPromisify.custom] = function promisifiedSetTimeout(timeout, arg) {
              return new _global.Promise(function setTimeoutExecutor(resolve) {
                addTimer(clock, {
                  func: resolve,
                  args: [arg],
                  delay: timeout
                });
              });
            };
          }
          clock.clearTimeout = function clearTimeout(timerId) {
            return clearTimer(clock, timerId, "Timeout");
          };
          clock.nextTick = function nextTick(func) {
            return enqueueJob(clock, {
              func,
              args: Array.prototype.slice.call(arguments, 1),
              error: clock.isNearInfiniteLimit ? new Error() : null
            });
          };
          clock.queueMicrotask = function queueMicrotask(func) {
            return clock.nextTick(func);
          };
          clock.setInterval = function setInterval(func, timeout) {
            timeout = parseInt(String(timeout), 10);
            return addTimer(clock, {
              func,
              args: Array.prototype.slice.call(arguments, 2),
              delay: timeout,
              interval: timeout
            });
          };
          clock.clearInterval = function clearInterval(timerId) {
            return clearTimer(clock, timerId, "Interval");
          };
          if (isPresent.setImmediate) {
            clock.setImmediate = /** @type {SetImmediate} */
            (function setImmediate(func) {
              return addTimer(clock, {
                func,
                args: Array.prototype.slice.call(arguments, 1),
                immediate: true
              });
            });
            if (typeof _global.Promise !== "undefined" && utilPromisify) {
              clock.setImmediate[utilPromisify.custom] = function promisifiedSetImmediate(arg) {
                return new _global.Promise(
                  function setImmediateExecutor(resolve) {
                    addTimer(clock, {
                      func: resolve,
                      args: [arg],
                      immediate: true
                    });
                  }
                );
              };
            }
            clock.clearImmediate = function clearImmediate(timerId) {
              return clearTimer(clock, timerId, "Immediate");
            };
          }
          clock.countTimers = function countTimers() {
            return (clock.timerHeap ? clock.timerHeap.timers.length : 0) + (clock.jobs || []).length;
          };
          clock.requestAnimationFrame = function requestAnimationFrame(func) {
            const result = addTimer(clock, {
              func,
              delay: getTimeToNextFrame(),
              get args() {
                return [fakePerformanceNow()];
              },
              animation: true
            });
            return Number(result);
          };
          clock.cancelAnimationFrame = function cancelAnimationFrame(timerId) {
            return clearTimer(clock, timerId, "AnimationFrame");
          };
          clock.runMicrotasks = function runMicrotasks() {
            runJobs(clock);
          };
          function durationToMs(duration) {
            const relativeTo = NativeTemporal.Instant.fromEpochMilliseconds(
              clock.now
            ).toZonedDateTimeISO(NativeTemporal.Now.timeZoneId());
            return duration.total({ unit: "millisecond", relativeTo });
          }
          function tickValueToMs(tickValue) {
            if (typeof tickValue === "number") {
              return tickValue;
            }
            if (isPresent.Temporal && tickValue !== null && typeof tickValue === "object" && typeof /** @type {TemporalDuration} */
            tickValue.total === "function") {
              return durationToMs(
                /** @type {TemporalDuration} */
                tickValue
              );
            }
            return parseTime(
              /** @type {string} */
              tickValue
            );
          }
          function createTickState(tickValue) {
            const msFloat = tickValueToMs(tickValue);
            const ms = Math.floor(msFloat);
            const remainder = nanoRemainder(msFloat);
            let nanosTotal = nanos + remainder;
            let tickTo = clock.now + ms;
            if (msFloat < 0) {
              throw new TypeError("Negative ticks are not supported");
            }
            if (nanosTotal >= 1e6) {
              tickTo += 1;
              nanosTotal -= 1e6;
            }
            return (
              /** @type {ClockState} */
              {
                msFloat,
                ms,
                nanosTotal,
                tickFrom: clock.now,
                tickTo,
                previous: clock.now,
                timer: null,
                firstException: null,
                oldNow: null
              }
            );
          }
          function applyClockChangeCompensation(state, oldNow, options) {
            if (oldNow !== clock.now) {
              const difference = clock.now - oldNow;
              state.tickFrom += difference;
              state.tickTo += difference;
              if (options && options.includePrevious) {
                state.previous += difference;
              }
            }
          }
          function runInitialJobs(state) {
            state.oldNow = clock.now;
            runJobs(clock);
            applyClockChangeCompensation(state, state.oldNow);
          }
          function runPostLoopJobs(state) {
            state.oldNow = clock.now;
            runJobs(clock);
            applyClockChangeCompensation(state, state.oldNow);
          }
          function selectNextTimerInRange(state) {
            state.timer = firstTimerInRange(
              clock,
              state.previous,
              state.tickTo
            );
            state.previous = state.tickFrom;
          }
          function runTimersInRange(state, isAsync, nextPromiseTick, compensationCheck) {
            state.timer = firstTimerInRange(
              clock,
              state.tickFrom,
              state.tickTo
            );
            while (state.timer && state.tickFrom <= state.tickTo) {
              if (hasTimer(clock, state.timer.id)) {
                state.tickFrom = state.timer.callAt;
                clock.now = state.timer.callAt;
                state.oldNow = clock.now;
                try {
                  runJobs(clock);
                  callTimer(clock, state.timer);
                } catch (e) {
                  state.firstException = state.firstException || e;
                }
                if (isAsync) {
                  originalSetTimeout(nextPromiseTick);
                  return true;
                }
                compensationCheck();
              }
              selectNextTimerInRange(state);
            }
            return false;
          }
          function finalizeTick(state, isAsync, resolve) {
            state.timer = firstTimerInRange(
              clock,
              state.tickFrom,
              state.tickTo
            );
            if (state.timer) {
              try {
                clock.tick(state.tickTo - clock.now);
              } catch (e) {
                state.firstException = state.firstException || e;
              }
            } else {
              clock.now = state.tickTo;
              nanos = state.nanosTotal;
            }
            if (state.firstException) {
              throw state.firstException;
            }
            if (isAsync) {
              resolve(clock.now);
            } else {
              return clock.now;
            }
          }
          function doTick(tickValue, isAsync, resolve, reject) {
            const state = createTickState(tickValue);
            nanos = state.nanosTotal;
            clock.duringTick = true;
            runInitialJobs(state);
            const compensationCheck = function() {
              applyClockChangeCompensation(state, state.oldNow, {
                includePrevious: true
              });
            };
            const nextPromiseTick = isAsync && function() {
              try {
                compensationCheck();
                selectNextTimerInRange(state);
                doTickInner();
              } catch (e) {
                reject(e);
              }
            };
            function doTickInner() {
              if (runTimersInRange(
                state,
                isAsync,
                nextPromiseTick,
                compensationCheck
              )) {
                return;
              }
              runPostLoopJobs(state);
              clock.duringTick = false;
              return finalizeTick(state, isAsync, resolve);
            }
            return doTickInner();
          }
          clock.tick = function tick(tickValue) {
            return doTick(tickValue, false);
          };
          clock.next = function next() {
            runJobs(clock);
            const timer = firstTimer(clock);
            if (!timer) {
              return clock.now;
            }
            clock.duringTick = true;
            try {
              clock.now = timer.callAt;
              callTimer(clock, timer);
              runJobs(clock);
              return clock.now;
            } finally {
              clock.duringTick = false;
            }
          };
          function runAsyncWithNativeTimeout(callback) {
            return pauseAutoTickUntilFinished(
              new _global.Promise(function(resolve, reject) {
                originalSetTimeout(function() {
                  try {
                    callback(resolve, reject);
                  } catch (e) {
                    reject(e);
                  }
                });
              })
            );
          }
          clock.runAll = function runAll() {
            runJobs(clock);
            for (let i = 0; i < clock.loopLimit; i++) {
              if (!clock.timers) {
                resetIsNearInfiniteLimit(clock);
                return clock.now;
              }
              const numTimers = clock.timerHeap.timers.length;
              if (numTimers === 0) {
                resetIsNearInfiniteLimit(clock);
                return clock.now;
              }
              checkIsNearInfiniteLimit(clock, i);
              clock.next();
            }
            const excessJob = firstTimer(clock);
            throw getInfiniteLoopError(clock, excessJob);
          };
          clock.runToFrame = function runToFrame() {
            return clock.tick(getTimeToNextFrame());
          };
          clock.runToLast = function runToLast() {
            const timer = lastTimer(clock);
            if (!timer) {
              runJobs(clock);
              return clock.now;
            }
            return clock.tick(timer.callAt - clock.now);
          };
          if (typeof _global.Promise !== "undefined") {
            clock.tickAsync = function tickAsync(tickValue) {
              return runAsyncWithNativeTimeout(function(resolve, reject) {
                doTick(tickValue, true, resolve, reject);
              });
            };
            clock.nextAsync = function nextAsync() {
              return runAsyncWithNativeTimeout(function(resolve, reject) {
                const timer = firstTimer(clock);
                if (!timer) {
                  resolve(clock.now);
                  return;
                }
                let err;
                clock.duringTick = true;
                clock.now = timer.callAt;
                try {
                  callTimer(clock, timer);
                } catch (e) {
                  err = e;
                }
                clock.duringTick = false;
                originalSetTimeout(function() {
                  if (err) {
                    reject(err);
                  } else {
                    resolve(clock.now);
                  }
                });
              });
            };
            clock.runAllAsync = function runAllAsync() {
              let i = 0;
              function doRun(resolve, reject) {
                try {
                  runJobs(clock);
                  let numTimers;
                  if (i < clock.loopLimit) {
                    if (!clock.timerHeap) {
                      resetIsNearInfiniteLimit(clock);
                      resolve(clock.now);
                      return;
                    }
                    numTimers = clock.timerHeap.timers.length;
                    if (numTimers === 0) {
                      resetIsNearInfiniteLimit(clock);
                      resolve(clock.now);
                      return;
                    }
                    checkIsNearInfiniteLimit(clock, i);
                    clock.next();
                    i++;
                    originalSetTimeout(function() {
                      doRun(resolve, reject);
                    });
                    return;
                  }
                  const excessJob = firstTimer(clock);
                  reject(getInfiniteLoopError(clock, excessJob));
                } catch (e) {
                  reject(e);
                }
              }
              return runAsyncWithNativeTimeout(function(resolve, reject) {
                doRun(resolve, reject);
              });
            };
            clock.runToLastAsync = function runToLastAsync() {
              return runAsyncWithNativeTimeout(function(resolve) {
                const timer = lastTimer(clock);
                if (!timer) {
                  runJobs(clock);
                  resolve(clock.now);
                  return;
                }
                resolve(clock.tickAsync(timer.callAt - clock.now));
              });
            };
          }
          clock.reset = function reset() {
            nanos = 0;
            clock.timers = /* @__PURE__ */ new Map();
            clock.timerHeap = new TimerHeap();
            clock.jobs = [];
            clock.now = start;
          };
          clock.setSystemTime = function setSystemTime(systemTime) {
            const newNow = getEpoch(systemTime);
            const difference = newNow - clock.now;
            adjustedSystemTime[0] = adjustedSystemTime[0] + difference;
            adjustedSystemTime[1] = adjustedSystemTime[1] + nanos;
            clock.now = newNow;
            nanos = 0;
            forEachActiveTimer(clock, (timer) => {
              timer.createdAt += difference;
              timer.callAt += difference;
            });
          };
          clock.jump = function jump(tickValue) {
            const msFloat = tickValueToMs(tickValue);
            const ms = Math.floor(msFloat);
            forEachActiveTimer(clock, (timer) => {
              if (clock.now + ms > timer.callAt) {
                timer.callAt = clock.now + ms;
              }
            });
            rebuildTimerHeap(clock);
            clock.tick(ms);
            return clock.now;
          };
          if (isPresent.performance) {
            clock.performance = /* @__PURE__ */ Object.create(null);
            clock.performance.now = fakePerformanceNow;
          }
          if (isPresent.hrtime) {
            clock.hrtime = hrtime;
          }
          clock.uninstall = function() {
            uninstalled = true;
            clock.setTickMode({ mode: "manual" });
            if (clock.methods) {
              const installedHrTime = "_hrtime";
              const installedNextTick = "_nextTick";
              let method, i, l;
              for (i = 0, l = clock.methods.length; i < l; i++) {
                method = clock.methods[i];
                if (method === "hrtime" && _global.process) {
                  _global.process.hrtime = clock[installedHrTime];
                } else if (method === "nextTick" && _global.process) {
                  _global.process.nextTick = clock[installedNextTick];
                } else if (method === "performance") {
                  const originalPerfDescriptor = Object.getOwnPropertyDescriptor(
                    clock,
                    `_${method}`
                  );
                  if (originalPerfDescriptor && originalPerfDescriptor.get && !originalPerfDescriptor.set) {
                    Object.defineProperty(
                      _global,
                      method,
                      originalPerfDescriptor
                    );
                  } else if (originalPerfDescriptor.configurable) {
                    _global[method] = clock[`_${method}`];
                  }
                } else {
                  if (clock[method] && clock[method].hasOwnProperty) {
                    _global[method] = clock[`_${method}`];
                  } else {
                    try {
                      delete _global[method];
                    } catch {
                    }
                  }
                }
                if (clock.timersModuleMethods !== void 0) {
                  for (let j = 0; j < clock.timersModuleMethods.length; j++) {
                    const entry = clock.timersModuleMethods[j];
                    timersModule[entry.methodName] = entry.original;
                  }
                }
                if (clock.timersPromisesModuleMethods !== void 0) {
                  for (let j = 0; j < clock.timersPromisesModuleMethods.length; j++) {
                    const entry = clock.timersPromisesModuleMethods[j];
                    timersPromisesModule[entry.methodName] = entry.original;
                  }
                }
              }
              clock.methods = [];
            }
            if (clock.abortListenerMap) {
              for (const [
                listener,
                signal
              ] of clock.abortListenerMap.entries()) {
                signal.removeEventListener("abort", listener);
                clock.abortListenerMap.delete(listener);
              }
            }
            if (!clock.timerHeap) {
              return [];
            }
            return clock.timerHeap.timers.slice();
          };
          return clock;
        }
        function createIntervalTick(clock, delta) {
          const intervalTick = doIntervalTick.bind(null, clock, delta);
          const intervalId = originalSetInterval(intervalTick, delta);
          clock.attachedInterval = intervalId;
        }
        function install(config) {
          if (arguments.length > 1 || config instanceof Date || Array.isArray(config) || typeof config === "number") {
            throw new TypeError(
              `FakeTimers.install called with ${String(
                config
              )} install requires an object parameter`
            );
          }
          if (_global.Date.isFake === true) {
            throw new TypeError(
              "Can't install fake timers twice on the same global object."
            );
          }
          config = typeof config !== "undefined" ? config : {};
          config.shouldAdvanceTime = config.shouldAdvanceTime || false;
          config.advanceTimeDelta = config.advanceTimeDelta || 20;
          config.shouldClearNativeTimers = config.shouldClearNativeTimers || false;
          const hasToFake = Object.prototype.hasOwnProperty.call(
            config,
            "toFake"
          );
          const hasToNotFake = Object.prototype.hasOwnProperty.call(
            config,
            "toNotFake"
          );
          if (hasToFake && hasToNotFake) {
            throw new TypeError(
              "config.toFake and config.toNotFake cannot be used together"
            );
          }
          if (config.target) {
            throw new TypeError(
              "config.target is no longer supported. Use `withGlobal(target)` instead."
            );
          }
          function handleMissingTimer(timer) {
            if (config.ignoreMissingTimers) {
              return;
            }
            throw new ReferenceError(
              `non-existent timers and/or objects cannot be faked: '${timer}'`
            );
          }
          let i, l;
          const clock = createClock(config.now, config.loopLimit);
          clock.shouldClearNativeTimers = config.shouldClearNativeTimers;
          clock.abortListenerMap = /* @__PURE__ */ new Map();
          if (hasToFake) {
            clock.methods = /** @type {FakeMethod[]} */
            config.toFake || [];
            if (clock.methods.length === 0) {
              clock.methods = /** @type {FakeMethod[]} */
              Object.keys(timers);
            }
          } else if (hasToNotFake) {
            const methodsToNotFake = (
              /** @type {string[]} */
              config.toNotFake || []
            );
            clock.methods = /** @type {FakeMethod[]} */
            Object.keys(timers).filter(
              (method) => !methodsToNotFake.includes(method)
            );
          } else {
            clock.methods = /** @type {FakeMethod[]} */
            Object.keys(timers);
          }
          if (config.shouldAdvanceTime === true) {
            clock.setTickMode({
              mode: "interval",
              delta: config.advanceTimeDelta
            });
          }
          if (clock.methods.includes("performance")) {
            const proto = (() => {
              if (hasPerformanceConstructorPrototype) {
                return _global.performance.constructor.prototype;
              }
              if (hasPerformancePrototype) {
                return _global.Performance.prototype;
              }
            })();
            if (proto) {
              Object.getOwnPropertyNames(proto).forEach(function(name) {
                if (name !== "now") {
                  clock.performance[name] = name.indexOf("getEntries") === 0 ? NOOP_ARRAY : NOOP;
                }
              });
              clock.performance.mark = (name) => new FakePerformanceEntry(name, "mark", 0, 0);
              clock.performance.measure = (name) => new FakePerformanceEntry(name, "measure", 0, 100);
              clock.performance.timeOrigin = getEpoch(config.now);
            } else if ((config.toFake || []).includes("performance")) {
              handleMissingTimer("performance");
            }
          }
          if (_global === globalObject && timersModule) {
            clock.timersModuleMethods = [];
          }
          if (_global === globalObject && timersPromisesModule) {
            clock.timersPromisesModuleMethods = [];
          }
          for (i = 0, l = clock.methods.length; i < l; i++) {
            const nameOfMethodToReplace = clock.methods[i];
            if (!isPresent[nameOfMethodToReplace]) {
              handleMissingTimer(nameOfMethodToReplace);
              continue;
            }
            if (nameOfMethodToReplace === "hrtime") {
              if (_global.process && typeof _global.process.hrtime === "function") {
                hijackMethod(_global.process, nameOfMethodToReplace, clock);
              }
            } else if (nameOfMethodToReplace === "nextTick") {
              if (_global.process && typeof _global.process.nextTick === "function") {
                hijackMethod(_global.process, nameOfMethodToReplace, clock);
              }
            } else {
              hijackMethod(_global, nameOfMethodToReplace, clock);
            }
            if (clock.timersModuleMethods !== void 0 && timersModule[nameOfMethodToReplace]) {
              const original = timersModule[nameOfMethodToReplace];
              clock.timersModuleMethods.push({
                methodName: nameOfMethodToReplace,
                original
              });
              timersModule[nameOfMethodToReplace] = _global[nameOfMethodToReplace];
            }
            if (clock.timersPromisesModuleMethods !== void 0) {
              if (nameOfMethodToReplace === "setTimeout") {
                clock.timersPromisesModuleMethods.push({
                  methodName: "setTimeout",
                  original: timersPromisesModule.setTimeout
                });
                timersPromisesModule.setTimeout = (delay, value, options = {}) => new Promise((resolve, reject) => {
                  const abort = () => {
                    options.signal.removeEventListener(
                      "abort",
                      abort
                    );
                    clock.abortListenerMap.delete(abort);
                    clock.clearTimeout(handle);
                    reject(options.signal.reason);
                  };
                  const handle = clock.setTimeout(() => {
                    if (options.signal) {
                      options.signal.removeEventListener(
                        "abort",
                        abort
                      );
                      clock.abortListenerMap.delete(abort);
                    }
                    resolve(value);
                  }, delay);
                  if (options.signal) {
                    if (options.signal.aborted) {
                      abort();
                    } else {
                      options.signal.addEventListener(
                        "abort",
                        abort
                      );
                      clock.abortListenerMap.set(
                        abort,
                        options.signal
                      );
                    }
                  }
                });
              } else if (nameOfMethodToReplace === "setImmediate") {
                clock.timersPromisesModuleMethods.push({
                  methodName: "setImmediate",
                  original: timersPromisesModule.setImmediate
                });
                timersPromisesModule.setImmediate = (value, options = {}) => new Promise((resolve, reject) => {
                  const abort = () => {
                    options.signal.removeEventListener(
                      "abort",
                      abort
                    );
                    clock.abortListenerMap.delete(abort);
                    clock.clearImmediate(handle);
                    reject(options.signal.reason);
                  };
                  const handle = clock.setImmediate(() => {
                    if (options.signal) {
                      options.signal.removeEventListener(
                        "abort",
                        abort
                      );
                      clock.abortListenerMap.delete(abort);
                    }
                    resolve(value);
                  });
                  if (options.signal) {
                    if (options.signal.aborted) {
                      abort();
                    } else {
                      options.signal.addEventListener(
                        "abort",
                        abort
                      );
                      clock.abortListenerMap.set(
                        abort,
                        options.signal
                      );
                    }
                  }
                });
              } else if (nameOfMethodToReplace === "setInterval") {
                clock.timersPromisesModuleMethods.push({
                  methodName: "setInterval",
                  original: timersPromisesModule.setInterval
                });
                timersPromisesModule.setInterval = (delay, value, options = {}) => ({
                  [Symbol.asyncIterator]: () => {
                    const createResolvable = () => {
                      let resolve, reject;
                      const promise = (
                        /** @type {Promise<unknown> & { resolve: (value: unknown) => void; reject: (reason: unknown) => void }} */
                        new Promise((res, rej) => {
                          resolve = res;
                          reject = rej;
                        })
                      );
                      promise.resolve = resolve;
                      promise.reject = reject;
                      return promise;
                    };
                    let done = false;
                    let hasThrown = false;
                    let returnCall;
                    let nextAvailable = 0;
                    const nextQueue = [];
                    const handle = clock.setInterval(() => {
                      if (nextQueue.length > 0) {
                        nextQueue.shift().resolve();
                      } else {
                        nextAvailable++;
                      }
                    }, delay);
                    const abort = () => {
                      options.signal.removeEventListener(
                        "abort",
                        abort
                      );
                      clock.abortListenerMap.delete(abort);
                      clock.clearInterval(handle);
                      done = true;
                      for (const resolvable of nextQueue) {
                        resolvable.resolve();
                      }
                    };
                    if (options.signal) {
                      if (options.signal.aborted) {
                        done = true;
                      } else {
                        options.signal.addEventListener(
                          "abort",
                          abort
                        );
                        clock.abortListenerMap.set(
                          abort,
                          options.signal
                        );
                      }
                    }
                    return {
                      next: async () => {
                        if (options.signal?.aborted && !hasThrown) {
                          hasThrown = true;
                          throw options.signal.reason;
                        }
                        if (done) {
                          return { done: true, value: void 0 };
                        }
                        if (nextAvailable > 0) {
                          nextAvailable--;
                          return { done: false, value };
                        }
                        const resolvable = createResolvable();
                        nextQueue.push(resolvable);
                        await resolvable;
                        if (returnCall && nextQueue.length === 0) {
                          returnCall.resolve();
                        }
                        if (options.signal?.aborted && !hasThrown) {
                          hasThrown = true;
                          throw options.signal.reason;
                        }
                        if (done) {
                          return { done: true, value: void 0 };
                        }
                        return { done: false, value };
                      },
                      return: async () => {
                        if (done) {
                          return { done: true, value: void 0 };
                        }
                        if (nextQueue.length > 0) {
                          returnCall = createResolvable();
                          await returnCall;
                        }
                        clock.clearInterval(handle);
                        done = true;
                        if (options.signal) {
                          options.signal.removeEventListener(
                            "abort",
                            abort
                          );
                          clock.abortListenerMap.delete(abort);
                        }
                        return { done: true, value: void 0 };
                      }
                    };
                  }
                });
              }
            }
          }
          return clock;
        }
        return {
          timers,
          createClock,
          install,
          withGlobal
        };
      }
      var defaultImplementation = withGlobal(globalObject);
      exports.timers = defaultImplementation.timers;
      exports.createClock = defaultImplementation.createClock;
      exports.install = defaultImplementation.install;
      exports.withGlobal = withGlobal;
    }
  });

  // entry.cjs
  var require_entry = __commonJS({
    "entry.cjs"(exports, module) {
      module.exports = require_fake_timers_src();
    }
  });
  return require_entry();
})();

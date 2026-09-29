import std/[os, strutils]

let
  viewerDir = currentSourcePath().parentDir
  engineRoot = getEnv("POLYWORLD_ENGINE")
  dependencyRoot = getEnv("POLYWORLD_DEPS")

if engineRoot.len == 0 or not dirExists(engineRoot / "src" / "polyworld"):
  quit("POLYWORLD_ENGINE must name a Metta-AI/polyworld checkout")
if dependencyRoot.len == 0 or not dirExists(dependencyRoot):
  quit("POLYWORLD_DEPS must name the pinned Polyworld dependency directory")

switch("path", engineRoot / "src")
for line in readFile(engineRoot / "coworld" / "dependencies.lock").splitLines():
  let fields = line.splitWhitespace()
  if fields.len == 0:
    continue
  let directory = dependencyRoot / fields[0]
  switch("path", if dirExists(directory / "src"): directory / "src" else: directory)

--define:nimTypeNames
--define:flatty64
when not defined(debug):
  --define:release
  --define:noAutoGLerrorCheck

when defined(emscripten):
  # The build script exports the same variables the Concordia viewer used, so
  # tools/build_polyworld_viewer.sh needs no viewer-specific changes.
  # LOVETOWN_* names are accepted as aliases.
  proc firstEnv(names: varargs[string], fallback = ""): string =
    for name in names:
      if getEnv(name).len > 0:
        return getEnv(name)
    fallback
  let
    outputDir = firstEnv(["LOVETOWN_POLYWORLD_OUTPUT", "CONCORDIA_POLYWORLD_OUTPUT"],
      viewerDir / "emscripten")
    replayPath = firstEnv(["LOVETOWN_POLYWORLD_REPLAY", "CONCORDIA_POLYWORLD_REPLAY"])
    shellFile = firstEnv(["LOVETOWN_POLYWORLD_SHELL"], viewerDir / "web_shell.html")
  if replayPath.len == 0 or not fileExists(replayPath):
    quit("CONCORDIA_POLYWORLD_REPLAY (or LOVETOWN_POLYWORLD_REPLAY) must name a love-town replay JSON")
  if not fileExists(shellFile):
    quit("web shell not found: " & shellFile)
  if not dirExists(outputDir):
    mkDir(outputDir)
  switch("nimcache", outputDir / "tmp")
  switch("threads", "off")
  --os:linux
  --cpu:wasm32
  --cc:clang
  --clang.exe:emcc
  --clang.linkerexe:emcc
  --clang.cpp.exe:emcc
  --clang.cpp.linkerexe:emcc
  --gc:arc
  --exceptions:goto
  --define:noSignalHandler
  let link = "-o " & quoteShell(outputDir / "main.html") &
    " --preload-file " & quoteShell(replayPath & "@/replay.json") &
    " --shell-file " & quoteShell(shellFile) &
    " -s ASYNCIFY -s FETCH -s EXIT_RUNTIME=1 -s USE_WEBGL2=1" &
    " -s MAX_WEBGL_VERSION=2 -s MIN_WEBGL_VERSION=1 -s FULL_ES3=1" &
    " -s EXPORTED_FUNCTIONS=_main,_lovetownCommand,_lovetownState" &
    " -s EXPORTED_RUNTIME_METHODS=FS,addRunDependency,removeRunDependency,ccall,cwrap,UTF8ToString,stringToUTF8,lengthBytesUTF8" &
    " -s GL_ENABLE_GET_PROC_ADDRESS=1 -s ALLOW_MEMORY_GROWTH --profiling"
  switch("passL", link)

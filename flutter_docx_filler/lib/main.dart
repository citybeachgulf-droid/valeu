import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';

import 'docx_filler.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  // This widget is the root of your application.
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'DOCX Filler',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blue),
      ),
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  String? templatePath;
  String? dataPath;
  String? outputPath; // for single
  String? outputDir; // for batch
  String? nameField;
  bool isBatch = false;
  String logText = '';
  bool busy = false;

  Future<void> _pickTemplate() async {
    final result = await FilePicker.platform.pickFiles(
      dialogTitle: 'Select DOCX template',
      type: FileType.custom,
      allowedExtensions: ['docx'],
    );
    if (result != null && result.files.single.path != null) {
      setState(() => templatePath = result.files.single.path);
    }
  }

  Future<void> _pickDataJson() async {
    final result = await FilePicker.platform.pickFiles(
      dialogTitle: 'Select JSON data file',
      type: FileType.custom,
      allowedExtensions: ['json'],
    );
    if (result != null && result.files.single.path != null) {
      setState(() => dataPath = result.files.single.path);
    }
  }

  Future<void> _pickOutputFile() async {
    // For simplicity, we will create a default path in documents dir
    final dir = await getApplicationDocumentsDirectory();
    final defaultPath = '${dir.path}${Platform.pathSeparator}output.docx';
    setState(() => outputPath = defaultPath);
  }

  Future<void> _pickOutputDir() async {
    final directoryPath = await FilePicker.platform.getDirectoryPath(
      dialogTitle: 'Select output directory',
    );
    if (directoryPath != null) {
      setState(() => outputDir = directoryPath);
    }
  }

  Future<void> _run() async {
    if (templatePath == null || dataPath == null) {
      _appendLog('Please select template and JSON data.');
      return;
    }
    setState(() => busy = true);
    try {
      if (isBatch) {
        if (outputDir == null) {
          await _pickOutputDir();
        }
        if (outputDir == null) {
          _appendLog('Please select output directory.');
          return;
        }
        final count = await DocxFiller.fillBatchFromJson(
          templatePath: templatePath!,
          dataJsonPath: dataPath!,
          outputDir: outputDir!,
          nameField: nameField?.trim().isEmpty == true ? null : nameField?.trim(),
        );
        _appendLog('Generated $count file(s) into $outputDir');
      } else {
        final out = outputPath ?? await _defaultSingleOutPath();
        await DocxFiller.fillSingleFromJson(
          templatePath: templatePath!,
          dataJsonPath: dataPath!,
          outputPath: out,
        );
        setState(() => outputPath = out);
        _appendLog('Wrote $out');
      }
    } catch (e, st) {
      _appendLog('Error: $e');
      _appendLog(st.toString());
    } finally {
      setState(() => busy = false);
    }
  }

  Future<String> _defaultSingleOutPath() async {
    final dir = await getApplicationDocumentsDirectory();
    return '${dir.path}${Platform.pathSeparator}output.docx';
  }

  void _appendLog(String line) {
    setState(() => logText = (logText.isEmpty ? line : '$logText\n$line'));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('DOCX Filler'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text('Template: ${templatePath ?? '-'}'),
                ),
                const SizedBox(width: 8),
                ElevatedButton(
                  onPressed: busy ? null : _pickTemplate,
                  child: const Text('Choose .docx'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: Text('Data JSON: ${dataPath ?? '-'}'),
                ),
                const SizedBox(width: 8),
                ElevatedButton(
                  onPressed: busy ? null : _pickDataJson,
                  child: const Text('Choose .json'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Switch(
                  value: isBatch,
                  onChanged: busy
                      ? null
                      : (v) {
                          setState(() => isBatch = v);
                        },
                ),
                const Text('Batch mode (array of objects)'),
                const Spacer(),
                if (!isBatch)
                  Expanded(
                    child: Text('Output: ${outputPath ?? '(default in Documents)'}'),
                  ),
                if (isBatch)
                  Expanded(
                    child: Text('Output dir: ${outputDir ?? '-'}'),
                  ),
                const SizedBox(width: 8),
                if (!isBatch)
                  ElevatedButton(
                    onPressed: busy ? null : _pickOutputFile,
                    child: const Text('Set output path'),
                  ),
                if (isBatch)
                  ElevatedButton(
                    onPressed: busy ? null : _pickOutputDir,
                    child: const Text('Choose out dir'),
                  ),
              ],
            ),
            if (isBatch) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  const Text('Name field (optional): '),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextField(
                      onChanged: (v) => nameField = v,
                      decoration: const InputDecoration(
                        hintText: 'e.g. INVOICE_NO',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                    ),
                  ),
                ],
              ),
            ],
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: busy ? null : _run,
                icon: busy
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.play_arrow),
                label: Text(busy ? 'Working...' : 'Run'),
              ),
            ),
            const SizedBox(height: 16),
            const Text('Log:'),
            Expanded(
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.grey.shade400),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: SingleChildScrollView(
                  child: Text(
                    logText,
                    style: const TextStyle(fontFamily: 'monospace'),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

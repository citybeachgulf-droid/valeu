import 'dart:convert';
import 'dart:io';

import 'package:archive/archive.dart';

class DocxFiller {
  static Future<void> fillSingle({
    required String templatePath,
    required Map<String, dynamic> mapping,
    required String outputPath,
  }) async {
    final templateBytes = await File(templatePath).readAsBytes();
    final originalArchive = ZipDecoder().decodeBytes(templateBytes);

    final newArchive = Archive();
    for (final file in originalArchive.files) {
      if (!file.isFile) {
        // Skip explicit directory entries; Zip will infer directories from paths.
        continue;
      }

      final name = file.name;
      final isXml = name.startsWith('word/') && name.toLowerCase().endsWith('.xml');
      final originalBytes = file.content as List<int>;

      List<int> bytesToWrite = originalBytes;
      if (isXml) {
        String text;
        try {
          text = utf8.decode(originalBytes, allowMalformed: true);
        } catch (_) {
          text = const Latin1Decoder().convert(originalBytes);
        }

        mapping.forEach((key, value) {
          final placeholder = '{${key.toString()}}';
          text = text.replaceAll(placeholder, value?.toString() ?? '');
        });

        bytesToWrite = utf8.encode(text);
      }

      newArchive.addFile(ArchiveFile(name, bytesToWrite.length, bytesToWrite));
    }

    final outBytes = ZipEncoder().encode(newArchive);
    final outFile = File(outputPath);
    await outFile.parent.create(recursive: true);
    await outFile.writeAsBytes(outBytes, flush: true);
  }

  static Future<void> fillSingleFromJson({
    required String templatePath,
    required String dataJsonPath,
    required String outputPath,
  }) async {
    final jsonString = await File(dataJsonPath).readAsString();
    final dynamic parsed = json.decode(jsonString);
    if (parsed is! Map<String, dynamic>) {
      throw ArgumentError('For single output, JSON must be an object.');
    }
    await fillSingle(
      templatePath: templatePath,
      mapping: parsed,
      outputPath: outputPath,
    );
  }

  static Future<int> fillBatchFromJson({
    required String templatePath,
    required String dataJsonPath,
    required String outputDir,
    String? nameField,
  }) async {
    final jsonString = await File(dataJsonPath).readAsString();
    final dynamic parsed = json.decode(jsonString);
    if (parsed is! List) {
      throw ArgumentError('For batch output, JSON must be an array of objects.');
    }

    int count = 0;
    for (int index = 0; index < parsed.length; index++) {
      final record = parsed[index];
      if (record is! Map<String, dynamic>) {
        continue;
      }

      String fileName;
      if (nameField != null && nameField.isNotEmpty && record.containsKey(nameField)) {
        var raw = (record[nameField] ?? '').toString().trim();
        if (raw.isEmpty) raw = '${index + 1}';
        fileName = 'output-${_sanitizeForFileName(raw)}.docx';
      } else {
        fileName = 'output-${index + 1}.docx';
      }

      final outPath = _joinPath(outputDir, fileName);
      await fillSingle(templatePath: templatePath, mapping: record, outputPath: outPath);
      count++;
    }

    return count;
  }

  static String _joinPath(String dir, String name) {
    if (dir.endsWith(Platform.pathSeparator)) return '$dir$name';
    return '$dir${Platform.pathSeparator}$name';
  }

  static String _sanitizeForFileName(String input) {
    // Replace path separators and common illegal filename chars on major OSes
    final sanitized = input
        .replaceAll('/', '-')
        .replaceAll('\\', '-')
        .replaceAll(RegExp(r'[\r\n\t]'), ' ')
        .replaceAll(RegExp(r'[<>:"|?*]'), '-')
        .trim();
    return sanitized.isEmpty ? 'output' : sanitized;
  }
}


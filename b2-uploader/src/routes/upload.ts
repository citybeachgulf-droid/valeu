import express from 'express';
import multer from 'multer';
import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { z } from 'zod';
import { buildPublicUrl, joinPathSegments, sanitizeFileName, uploadFileToB2 } from '../lib/b2.js';

const router = express.Router();

const CATEGORIES = [
	'company-docs', // مستندات الشركة
	'bank-messages', // رسائل البنوك
	'sales-invoices', // فواتير البيع
	'bank-invoices', // فواتير البنوك
] as const;

const uploadDir = path.join(process.cwd(), '.tmp', 'uploads');
fs.mkdirSync(uploadDir, { recursive: true });

const storage = multer.diskStorage({
	destination: (_req, _file, cb) => cb(null, uploadDir),
	filename: (_req, file, cb) => cb(null, `${Date.now()}--${sanitizeFileName(file.originalname)}`),
});

const upload = multer({
	storage,
	limits: { fileSize: 1024 * 1024 * 200 }, // 200MB per file (adjust as needed)
});

const BodySchema = z.object({
	category: z.enum(CATEGORIES),
	subfolder: z.string().optional(),
});

router.post('/upload', upload.single('file'), async (req, res, next) => {
	try {
		if (!req.file) {
			return res.status(400).json({ error: 'file is required (multipart form field: file)' });
		}
		const parsed = BodySchema.safeParse({
			category: (req.body?.category ?? '').toString(),
			subfolder: req.body?.subfolder?.toString(),
		});
		if (!parsed.success) {
			return res.status(400).json({ error: 'Invalid body', details: parsed.error.flatten() });
		}
		const { category, subfolder } = parsed.data;

		const now = new Date();
		const yyyy = now.getFullYear();
		const mm = String(now.getMonth() + 1).padStart(2, '0');
		const dd = String(now.getDate()).padStart(2, '0');
		const random = typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `${Date.now()}`;
		const original = sanitizeFileName(req.file.originalname);
		const b2FileName = joinPathSegments(
			category,
			`${yyyy}/${mm}/${dd}`,
			subfolder ?? '',
			`${random}--${original}`
		);

		const result = await uploadFileToB2({
			filePath: req.file.path,
			fileName: b2FileName,
			mimeType: req.file.mimetype,
		});

		// Remove temp file after upload
		fs.promises.unlink(req.file.path).catch(() => {});

		const publicUrl = buildPublicUrl(result.fileName);
		return res.status(201).json({
			fileId: result.fileId,
			fileName: result.fileName,
			category,
			publicUrl,
			size: result.contentLength,
			mime: result.contentType,
			uploadedAt: new Date().toISOString(),
		});
	} catch (err) {
		next(err);
	}
});

export default router;


import B2 from 'backblaze-b2';
import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { env } from './env.js';

const b2 = new B2({
	applicationKeyId: env.B2_KEY_ID,
	applicationKey: env.B2_APPLICATION_KEY,
});

async function authorizeIfNeeded(): Promise<void> {
	// The SDK caches auth; calling authorize repeatedly is fine
	await b2.authorize();
}

export async function computeSha1(filePath: string): Promise<string> {
	return new Promise((resolve, reject) => {
		const hash = crypto.createHash('sha1');
		const stream = fs.createReadStream(filePath);
		stream.on('data', (chunk) => hash.update(chunk));
		stream.on('error', reject);
		stream.on('end', () => resolve(hash.digest('hex')));
	});
}

export type UploadResult = {
	fileId: string;
	fileName: string;
	contentLength: number;
	contentType: string | undefined;
};

export async function uploadFileToB2(params: {
	filePath: string;
	fileName: string;
	mimeType?: string;
}): Promise<UploadResult> {
	await authorizeIfNeeded();
	const stat = await fs.promises.stat(params.filePath);
	const sha1 = await computeSha1(params.filePath);
	const { data: uploadUrlData } = await b2.getUploadUrl({ bucketId: env.B2_BUCKET_ID });
	const { uploadUrl, authorizationToken } = uploadUrlData;
	const dataStream = fs.createReadStream(params.filePath);
	const { data } = await b2.uploadFile({
		uploadUrl,
		uploadAuthToken: authorizationToken,
		fileName: params.fileName,
		data: dataStream as unknown as Buffer, // SDK accepts stream
		contentLength: stat.size,
		mime: params.mimeType ?? 'b2/x-auto',
		sha1,
	});
	return {
		fileId: data.fileId,
		fileName: data.fileName,
		contentLength: stat.size,
		contentType: params.mimeType,
	};
}

export function buildPublicUrl(fileName: string): string {
	// B2 friendly download URL: https://fXXX.backblazeb2.com/file/<bucketName>/<fileName>
	const encodedPath = fileName
		.split('/')
		.filter(Boolean)
		.map((seg) => encodeURIComponent(seg))
		.join('/');
	return `${env.B2_DOWNLOAD_URL}/${encodedPath}`;
}

export function joinPathSegments(...segments: string[]): string {
	return segments
		.map((s) => s.replace(/^[\/]+|[\/]+$/g, ''))
		.filter(Boolean)
		.join('/');
}

export function sanitizeFileName(originalName: string): string {
	const base = path.basename(originalName);
	return base
		.replace(/\s+/g, '_')
		.replace(/[^a-zA-Z0-9._-]/g, '')
		.replace(/_+/g, '_')
		.substring(0, 180);
}


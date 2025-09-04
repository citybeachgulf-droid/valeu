import dotenv from 'dotenv';
import { z } from 'zod';

dotenv.config();

const EnvSchema = z.object({
	B2_KEY_ID: z.string().min(1, 'B2_KEY_ID is required'),
	B2_APPLICATION_KEY: z.string().min(1, 'B2_APPLICATION_KEY is required'),
	B2_BUCKET_ID: z.string().min(1, 'B2_BUCKET_ID is required'),
	B2_BUCKET_NAME: z.string().min(1, 'B2_BUCKET_NAME is required'),
	B2_DOWNLOAD_URL: z
		.string()
		.url('B2_DOWNLOAD_URL must be a valid URL')
		.transform((s) => s.replace(/\/$/, '')),
	PORT: z
		.string()
		.default('4000')
		.transform((v) => Number(v))
		.pipe(z.number().int().positive()),
	ALLOW_ORIGIN: z.string().default('*'),
});

export const env = EnvSchema.parse(process.env);


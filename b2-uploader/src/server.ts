import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import morgan from 'morgan';
import { env } from './lib/env.js';
import uploadRouter from './routes/upload.js';

const app = express();

app.use(helmet());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));
app.use(
	cors({
		origin: env.ALLOW_ORIGIN === '*' ? true : env.ALLOW_ORIGIN,
	})
);
app.use(morgan('tiny'));

app.get('/health', (_req, res) => {
	res.json({ ok: true, ts: Date.now() });
});

app.use('/api', uploadRouter);

// Error handler
// eslint-disable-next-line @typescript-eslint/no-unused-vars
app.use((err: unknown, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
	console.error(err);
	res.status(500).json({ error: 'Internal Server Error' });
});

app.listen(env.PORT, () => {
	console.log(`B2 uploader running on http://localhost:${env.PORT}`);
});


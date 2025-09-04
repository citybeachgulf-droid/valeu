declare module 'backblaze-b2' {
	interface B2ConstructorOptions {
		applicationKeyId: string;
		applicationKey: string;
	}

	interface GetUploadUrlResponse {
		data: {
			uploadUrl: string;
			authorizationToken: string;
		};
	}

	interface UploadFileParams {
		uploadUrl: string;
		uploadAuthToken: string;
		fileName: string;
		data: Buffer;
		sha1?: string;
		mime?: string;
		contentLength?: number;
	}

	interface UploadFileResponse {
		data: {
			fileId: string;
			fileName: string;
		};
	}

	class B2 {
		constructor(options: B2ConstructorOptions);
		authorize(): Promise<void>;
		getUploadUrl(args: { bucketId: string }): Promise<GetUploadUrlResponse>;
		uploadFile(args: UploadFileParams): Promise<UploadFileResponse>;
	}

	export default B2;
}


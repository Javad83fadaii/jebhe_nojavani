# خلاصه پروژه «جبهه نوجوانی» (JebheNojavani) برای هوش مصنوعی

## ۱) معرفی کلی
پلتفرم آموزشی و گیمیفیکیشن فارسی (RTL) برای نوجوانان، با سه بخش اصلی:
1. سیر مطالعاتی (Learning): مرحله‌به‌مرحله، آزمون و کسب امتیاز
2. چالش‌ها (Challenges): ارسال فعالیت و دریافت سکه
3. جبهه بازار (jebhe_bazar): فروشگاه و مارکت‌پلیس با پنل فروشنده

سه «ارز» داخل سیستم وجود دارد:
- امتیاز (total_points): فقط از قبولی در مراحل سیر مطالعاتی. هر مرحله ۱۰۰ امتیاز و هر درجه ۱۰۰۰ امتیاز است.
- سکه چالش (challenge_coins): از چالش‌ها. در بازار خرج می‌شود یا ۱ به ۱ به تومان کیف پول تبدیل می‌شود.
- کیف پول (wallet_balance): تومان. شارژ آن دستی و با تایید ادمین است.

## ۲) Stack
- Python 3.12، Django 6.0.4، Django REST Framework، SimpleJWT (با blacklist)
- PostgreSQL (با dj-database-url)، WhiteNoise، django-q2 (ORM broker)
- پیامک: SMS.ir (verify template با fallback به bulk)
- تصحیح هوشمند سوال تشریحی: API سازگار با OpenAI (GapGPT، مدل gpt-4o-mini)
- فرانت: Django templates، CSS دستی (glassmorphism، فونت Manshoor)، vanilla JS، jQuery و persian-datepicker فقط در صفحه ثبت‌نام و پروفایل
- دیپلوی: Liara (liara.json)
- لاگ: RotatingFileHandler

## ۳) ساختار اپ‌ها
- config: settings، urls، views (home/index/challenges/profile/auth pages)، middleware (محدودسازی IP ادمین)، context_processors، jalali.py، upload_security.py
- accounts: User (شماره موبایل = username)، Rank (۱۳ درجه از «افسر ۶» تا «مدال جبهه»)، Seller، CoinTransaction، CoinToWalletTransfer، PasswordResetRequest، سرویس‌های SMS، throttles، signals
- geography: Province، City، School، Mosque و APIهای عمومی lookup
- learning: LearningPath، LearningStage، StageQuestionSet (۳ مجموعه برای هر مرحله)، StageQuestion (چهارگزینه‌ای، صحیح/غلط، کوتاه‌پاسخ، تشریحی)، UserLearningProgress، UserStageProgress، UserStageExam، UserExamAnswer، ai_grader.py
- challenges: Challenge و ChallengeParticipation. انواع ارسال: حضور، متن، عکس، ویدیو. ادمین بعد از پایان چالش تایید می‌کند و سکه می‌دهد. فایل‌ها در private storage هستند و فقط از طریق view دانلود می‌شوند.
- jebhe_bazar: Category (درختی)، Product (پرداخت coin/money/both، تخفیف، بلیط)، Cart، CartItem، Order، OrderItem، Transaction، WalletChargeRequest، پنل فروشنده

## ۴) امکانات موجود
- ثبت‌نام و ورود با موبایل (session و JWT همزمان)، بازیابی رمز با OTP پیامکی (هش‌شده، حداکثر ۵ تلاش، انقضای ۵ دقیقه)
- تبدیل ارقام فارسی و عربی، تاریخ تولد جلالی (فقط متولدین ۱۳۸۵ تا ۱۳۹۵)
- throttle برای login، register و password reset (بر اساس IP و شماره)
- پروفایل، ویرایش، انتخاب مدرسه و مسجد و تبدیل سکه به کیف پول (درخواست و تایید ادمین)
- جدول امتیازات (با نام اختصاری) و درجه‌بندی ۱۳ سطحه
- سیر مطالعاتی: قفل‌گشایی مرحله‌ها به ترتیب، آزمون ۳۰ دقیقه‌ای، انتخاب تصادفی یکی از ۳ مجموعه سوال، حداقل نمره قبولی ۱۴ از ۲۰
- تصحیح AI برای سوال تشریحی با cache و fallback
- چالش‌ها: countdown، تب «چالش‌های من»، آپلود امن با بررسی magic bytes
- بازار: فیلتر و مرتب‌سازی، سبد خرید با AJAX stepper، checkout، پرداخت با سکه یا کیف پول، تسویه خودکار فروشنده با کمیسیون، لغو و استرداد از ادمین، سوابق سفارش، داشبورد فروشنده
- موبایل: bottom dock و sheet «بیشتر»
- تست‌های متعدد برای accounts، bazar، learning، challenges و config

## ۵) مشکلات و باگ‌های پیدا شده (به ترتیب اولویت)

### بحرانی / امنیتی
1. Province و City در صفحه ثبت‌نام کار نمی‌کنند. ProvinceListView و CityListView از `_paginate_lookup_items` استفاده می‌کنند و dict با `results` برمی‌گردانند، ولی JS در `templates/auth.html` شرط `Array.isArray(res.data)` دارد. نتیجه: dropdown استان و شهر خالی می‌ماند. تست `test_city_list_supports_ids` در geography/tests.py هم لیست انتظار دارد و احتمالاً fail می‌شود. باید JS و تست با `results` هماهنگ شوند یا pagination برداشته شود.
2. User enumeration در بازیابی رمز: برای شماره موجود در ۵ دقیقه اول، درخواست دوم ۴۲۹ می‌دهد (چون PasswordResetRequest ساخته شده). برای شماره ناموجود همیشه ۲۰۰ برمی‌گردد. cooldown باید مستقل از وجود کاربر باشد (مثلاً با cache به ازای شماره).
3. دور زدن throttle و IP allowlist با جعل `X-Forwarded-For`:
   - `NUM_PROXIES` در REST_FRAMEWORK تنظیم نشده.
   - `AdminAccessMiddleware` و `_get_client_ip` اولین مقدار XFF را اعتماد می‌کنند.
   - باید `NUM_PROXIES` ست شود و IP از proxy قابل اعتماد گرفته شود.
4. Cache پیش‌فرض LocMem است (CACHES تعریف نشده). با چند worker:
   - rate limitها per-process هستند و با restart ریست می‌شوند.
   - cache درجه‌ها (Rank) بعد از ویرایش ادمین در بقیه workerها تا ۱ ساعت قدیمی می‌ماند.
   - locking سینک سیر مطالعاتی و cache سبد خرید هم ناهماهنگ می‌شوند.
   باید Redis یا DB cache تنظیم شود.
5. `processed_at` در action ادمین `approve_transfers` و `reject_transfers` ذخیره نمی‌شود. signal مقدار را روی instance می‌گذارد ولی `save(update_fields=["status","updated_at"])` آن را نمی‌نویسد.
6. پردازش تایید انتقال سکه داخل signal `post_save` انجام می‌شود. اگر ValidationError بیفتد، وضعیت APPROVED ذخیره شده ولی سکه کسر نشده (action اتمیک نیست). این منطق باید به یک تابع service با `transaction.atomic` و `select_for_update` منتقل شود.
7. ثبت‌نام بدون تایید شماره موبایل (OTP) است، در حالی که سکه قابل تبدیل به پول است. این یعنی ریسک جعل حساب چندگانه برای سکه‌خواری. زیرساخت SMS آماده است.
8. ریسک اقتصادی: سکه رایگان از چالش به تومان واقعی فروشنده تبدیل می‌شود (تسویه ۱ به ۱) و فروشنده می‌تواند آن را برداشت کند. محدودیت و بازبینی لازم است.
9. media و فایل‌ها:
   - `PRIVATE_MEDIA_ROOT = BASE_DIR/private_media` از env خوانده نمی‌شود و روی دیسک پایدار Liara نیست. شواهد چالش با هر deploy از بین می‌رود.
   - `/media/` فقط در DEBUG سرو می‌شود. در production عکس محصول، کاور و پروفایل 404 می‌دهد، مگر وب‌سرور یا object storage جدا تنظیم شود.
10. آپلودهای بدون `UploadPolicyValidator`: User.profile_image، Seller.logo، LearningPath.cover_image، Rank.icon. از طریق PATCH پروفایل یا فروشنده قابل آپلود است.
11. XSS در `profile.html`: داده‌های سرور (نام، شهر، مدرسه، نام درجه، رنگ) با innerHTML بدون escape درج می‌شوند. تابع `escapeHtml` در base.html موجود است.
12. `.env.example` با parser دستی settings.py سازگار نیست. parser کامنت inline را حذف نمی‌کند. مثلاً `AI_GRADING_API_KEY=  #` مقدار «#» می‌شود و `AI_GRADING_BASE_URL=... # ` آدرس خراب می‌سازد. باید کامنت‌ها از مقدارها جدا شوند یا از python-dotenv استفاده شود.
13. کد تایید پیامک به‌صورت plaintext در آرگومان task جدول django-q ذخیره می‌شود.

### منطقی / داده
14. cart_ui برای ۶۰ ثانیه cache می‌شود و بعد از افزودن یا حذف آیتم invalidate نمی‌شود. badge سبد خرید کهنه می‌ماند و تست‌ها هم ممکن است flaky شوند. باید با signal روی CartItem پاک شود یا cache حذف شود.
15. کمیسیون فروشنده در OrderItem ذخیره نمی‌شود. `seller_commission` از درصد فعلی Seller محاسبه می‌شود. اگر نرخ بعد از خرید تغییر کند، مبلغ لغو و استرداد اشتباه می‌شود. باید `commission_percent` و مبلغ در لحظه خرید ذخیره شود.
16. مشکلات مایگریشن (احتمالی، با `makemigrations --check` تایید شود):
    - فیلدهای `legacy_requested_coins` و `granted_amount` در WalletChargeRequest و `gateway_paid_amount` در Order با `db_column` تعریف شده‌اند. مایگریشن‌ها هنوز نام قدیمی (`requested_coins`، `granted_coins`، `online_paid`) را در state دارند.
    - UniqueConstraint (parent,name) در Category در مایگریشن نیست و مایگریشن هنوز `name unique=True` دارد.
    - choices مربوط به REFUND در Transaction و CoinTransaction مایگریشن ندارد.
17. `start_exam` اتمیک نیست و با دابل‌کلیک ممکن است دو آزمون بسازد. باید روی stage progress قفل بگیرد.
18. «ثبت اتمام مطالعه» هیچ محدودیت زمانی ندارد (estimated_study_time نادیده گرفته می‌شود)، و تعداد دفعات آزمون و cooldown ندارد. دانش‌آموز می‌تواند هر سه مجموعه را حفظ کند. صفحه «سوالات مرحله» هم سوالات واقعی را قبل از آزمون نشان می‌دهد.
19. fallback تصحیح AI (وقتی کلید یا سرویس در دسترس نیست) تا ۷۰٪ شباهت می‌دهد، یعنی دقیقاً نمره قبولی (۱۴ از ۲۰). با کلمه‌چینی قابل بهره‌برداری است. بهتر است وضعیت «نیازمند بازبینی دستی» داشته باشد. تصحیح AI هم همزمان داخل request انجام می‌شود (تا حدود ۲۴ ثانیه) و ممکن است timeout gunicorn را بزند.
20. جمع نمره سوالات هر مجموعه اعتبارسنجی نمی‌شود که ۲۰ باشد. در سوال چهارگزینه‌ای هم پاسخ صحیح به‌صورت متن ذخیره می‌شود و با تغییر متن گزینه خراب می‌شود.
21. سینک مجموع مراحل و امتیاز: با هر save یا delete مرحله، سینک برای همه کاربران ثبت‌نام‌شده اجرا می‌شود (O(users × stages)). lock هم per-process است. اگر مرحله‌ای حذف یا غیرفعال شود، total_points کاربر برگردانده نمی‌شود و command بازمحاسبه ندارد.
22. تاریخ تولد مجاز (۱۳۸۵ تا ۱۳۹۵) در model، serializer و دو JS هاردکد شده و با گذر زمان کهنه می‌شود. باید بر اساس سن یا setting باشد.
23. `UserProfileSerializer`:
    - کد ملی در PATCH چک checksum ندارد (فقط در ثبت‌نام چک می‌شود).
    - فیلدهای bio و study_goal در مدل هستند ولی در API یا UI استفاده نمی‌شوند.
    - شهر و استان در پروفایل متن آزاد است ولی در ثبت‌نام dropdown.
24. `ChallengeParticipationSerializer`: فیلدهای submission_text، attended و evidence در create قابل نوشتن‌اند و باید read_only شوند. همچنین دابل‌کلیک ممکن است IntegrityError بدهد.
25. `Order` در ادمین کاملاً قابل ویرایش است (coins_used و غیره) و می‌تواند با آیتم‌ها ناسازگار شود. باید readonly شود.
26. توکن‌های refresh فقط وقتی blacklist می‌شوند که کلاینت ارسال کند. UI از JWT استفاده نمی‌کند و کد localStorage مرده است. دو سیستم احراز هویت (session و JWT) همزمان وجود دارد و باید یکی انتخاب شود. جدول blacklist هم به cleanup دوره‌ای (`flushexpiredtokens`) نیاز دارد.
27. اگر worker مربوط به django-q (`python manage.py qcluster`) روی Liara اجرا نشود، پیامک بازیابی رمز هرگز ارسال نمی‌شود، در حالی که API پاسخ ۲۰۰ می‌دهد.
28. وابستگی‌ها:
    - فونت Inter از Google Fonts با `@import`.
    - Font Awesome از cdnjs.
    - jQuery و datepicker از jsdelivr.
    این‌ها برای کاربران ایران کند یا مسدود می‌شوند. باید self-host شوند.
29. CompressedManifestStaticFilesStorage اگر فایل static ارجاع‌شده‌ای نباشد در production خطا می‌دهد. قبل از deploy باید `collectstatic` و بررسی انجام شود.
30. مشکلات کیفیت کد و تست:
    - در accounts/tests.py بلوک `too_new_payload` به‌اشتباه ته تست دیگری رفته است.
    - تست challenges از `timezone.timedelta` استفاده می‌کند. بهتر است `datetime.timedelta` باشد.
    - `from django.http import HttpResponse` در config/urls.py استفاده نمی‌شود.
    - در accounts/models.py نوع‌های `Iterable` و `Any` import نشده‌اند (فعلاً به‌خاطر `from __future__ import annotations` خطا نمی‌دهد).
    - فیلتر `toman` برای اعداد غیرپولی هم استفاده می‌شود، نام آن گمراه‌کننده است.
31. UI و CSS:
    - بخش بزرگی از CSS داخل template به‌صورت inline است (challenges، profile، index، learning).
    - `!important` و override زیاد وجود دارد (product_detail و unified-card-surfaces).
    - `.btn-primary` و متغیرهای `:root` در چند فایل با مقادیر متفاوت تعریف شده‌اند.
    - Font Awesome در index.html دو بار لود می‌شود.
    - متن‌های home.html درباره «چالش روزانه و مینی‌گیم» و «تبدیل امتیاز به جایزه» با قابلیت‌های واقعی (سکه، نه امتیاز) نمی‌خواند.

## ۶) کارهایی که باید انجام شود (TODO پیشنهادی)
فوری:
- رفع مشکل ۱، ۲، ۳، ۴، ۵، ۶، ۹، ۱۰، ۱۱ و ۱۲ بالا
- اجرای `makemigrations --check` و ساخت مایگریشن‌های جاافتاده، سپس اجرای کل تست‌ها
- راه‌اندازی worker برای django-q روی Liara
میان‌مدت:
- OTP برای ثبت‌نام
- ذخیره کمیسیون در OrderItem
- cooldown و سقف تعداد آزمون، حداقل زمان مطالعه، تصحیح تشریحی asynchronous، وضعیت «نیازمند بازبینی»
- invalidate شدن cache سبد خرید
- management command برای بازمحاسبه امتیاز
- self-host کردن فونت و کتابخانه‌ها
بلندمدت:
- درگاه پرداخت واقعی (مثل زرین‌پال)، چون `gateway_paid_amount` الان همیشه صفر است
- مدیریت وضعیت سفارش و آدرس تحویل برای کالای فیزیکی
- صدور بلیط یا کد QR برای محصولات تفریحی (`is_ticket`)، چون الان صفحه داشبورد فروشنده فقط placeholder QR دارد و فیلد qr_code وجود ندارد
- امتیازدهی و نظر برای فروشنده (فیلد rating استفاده نمی‌شود)
- اعلان‌ها، کوپن تخفیف، wishlist

## ۷) پیشنهادات بهبود
- Redis برای cache، throttle و broker
- Sentry و health-check
- CI با pytest، coverage و lint (ruff)
- CSP و self-host کردن همه assetها
- یکپارچه‌سازی CSS در فایل‌های static و design tokens مشترک
- نام‌گذاری سه ارز (امتیاز، سکه، تومان) و توضیح روشن در UI
- یک service layer برای عملیات مالی (سکه و کیف پول) به‌جای signal و منطق پخش در view و admin
- ثبت ledger یکپارچه برای تراکنش‌های مالی (الان CoinTransaction و Transaction جدا هستند)
- backup خودکار دیتابیس و media
- اضافه کردن index برای فیلدهای پرکاربرد (Challenge.start/end/is_active، Product.is_active و غیره)

## ۸) قواعد کار با من (کاربر)
- فارسی جواب بده و اصطلاحات فنی را انگلیسی نگه دار.
- فایل را کامل و آماده‌ی استفاده برگردان، نه diff یا توضیح ناقص. مسیر دقیق فایل را بگو.
- هر مشکلی که در کد دیدی را خودت اعلام کن، فقط مورد پرسیده‌شده را جواب نده.
- پاسخ‌های عملی و قابل پیاده‌سازی بده.
- نکته: این خلاصه فقط از روی فایل‌هایی نوشته شده که ارسال شده بود. فایل‌هایی مثل `templates/partials` و بعضی templateها را ندیده‌ام. قبل از تغییر، فایل مربوطه را بخواه.

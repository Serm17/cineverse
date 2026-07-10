import { useState } from 'react';

import { registerWithEmail } from '../../api.js';
import data from '/src/imgData.json';
import '../login/login.css';
import './signup.css';

const initialForm = {
  email: '',
  nickname: '',
  password: '',
  passwordConfirm: '',
};

function SignupPage() {
  const [form, setForm] = useState(initialForm);
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);

  const promos = data.hero.promos.slice(0, 4);

  const updateField = (event) => {
    const { name, value } = event.target;

    setForm((currentForm) => ({
      ...currentForm,
      [name]: value,
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    const email = form.email.trim();
    const nickname = form.nickname.trim();
    const password = form.password.trim();
    const passwordConfirm = form.passwordConfirm.trim();

    if (!email || !nickname || !password || !passwordConfirm) {
      setStatus('모든 항목을 입력해 주세요.');
      return;
    }

    if (!email.includes('@') || password.length < 6) {
      setStatus('이메일과 비밀번호를 다시 확인해 주세요.');
      return;
    }

    if (password !== passwordConfirm) {
      setStatus('비밀번호가 일치하지 않습니다.');
      return;
    }

    setBusy(true);
    setStatus('');

    try {
      await registerWithEmail({
        email,
        nickname,
        password,
      });

      setStatus('회원가입 성공. 로그인 페이지로 이동합니다.');
      window.setTimeout(() => {
        window.location.href = '/login';
      }, 700);
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="login-page signup-page" aria-label="회원가입">
      <section className="login-showcase" aria-label="CineVerse 추천 포스터">
        <div className="login-showcase__copy">
          <p>CINEVERSE</p>
          <h1>새로운 영화 취향을 시작하기</h1>
        </div>

        <div className="login-poster-grid" aria-hidden="true">
          {promos.map((promo) => (
            <img
              className="login-poster-grid__image"
              src={promo.image}
              alt=""
              key={promo.id}
            />
          ))}
        </div>
      </section>

      <section className="login-form-panel" aria-label="회원가입 입력">
        <div className="login-form-panel__header">
          <span>Create account</span>
          <h2>회원가입</h2>
        </div>

        <form className="login-form signup-form" onSubmit={handleSubmit}>
          <label className="login-field">
            <span>이메일</span>
            <input
              autoComplete="email"
              disabled={busy}
              name="email"
              onChange={updateField}
              placeholder="user1@example.com"
              type="email"
              value={form.email}
            />
          </label>

          <label className="login-field">
            <span>닉네임</span>
            <input
              autoComplete="nickname"
              disabled={busy}
              name="nickname"
              onChange={updateField}
              placeholder="user1"
              type="text"
              value={form.nickname}
            />
          </label>

          <label className="login-field">
            <span>비밀번호</span>
            <input
              autoComplete="new-password"
              disabled={busy}
              name="password"
              onChange={updateField}
              placeholder="6자 이상"
              type="password"
              value={form.password}
            />
          </label>

          <label className="login-field">
            <span>비밀번호 확인</span>
            <input
              autoComplete="new-password"
              disabled={busy}
              name="passwordConfirm"
              onChange={updateField}
              placeholder="비밀번호 재입력"
              type="password"
              value={form.passwordConfirm}
            />
          </label>

          {status ? (
            <p className="login-status" role="status">
              {status}
            </p>
          ) : null}

          <button className="login-submit" type="submit" disabled={busy}>
            {busy ? '가입 중' : '회원가입'}
          </button>
        </form>

        <p className="login-join">
          이미 계정이 있다면 <a href="/login">로그인</a>
        </p>
      </section>
    </main>
  );
}

export default SignupPage;
